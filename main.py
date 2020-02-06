import requests
import json
import ratelimit
import networkx as nx
import gui
import PyInquirer

from pymongo import MongoClient

# MONGO_URI = 'localhost:27017'
# MONGO_URI = 'mongodb://127.0.0.1:27017'
MONGO_CLIENT = MongoClient('localhost', 27016)
MONGO_DB = MONGO_CLIENT['CiteGraph']

@ratelimit.rate_limited(10) # calls per second
def rl_get(*args, **kwargs):
    '''rate-limited requests.get'''
    return requests.get(*args, **kwargs)

S_PAPER_URI = 'http://api.semanticscholar.org/v1/paper/'
def paper_from_paperid(paperid, collection_name='papers', refresh=False):
    '''query Semantic Semantic Scholar for a paper ID'''
    collection = MONGO_DB[collection_name]

    # try to get a cached entry
    if collection and not refresh:
        rv = collection.find_one({'_id': paperid})
        if rv is not None:
            return rv

    # query SemanticScholar
    query = S_PAPER_URI + paperid
    response = rl_get(query, timeout=5)
    if response.status_code != 200:
        return None

    dct = response.json()

    # cache the response
    dct['_id'] = paperid
    if collection:
        collection.insert_one(dct)
    return dct

def get_topics():
    '''return a list of all stored topics'''
    return [topic['_id'] for topic in MONGO_DB['topics'].find()]

def print_topics():
    '''print all topics to stdout'''
    topics = get_topics()
    if len(topics):
        print('Topics:')
    else:
        print('There are no stored topics')
    for topic in topics:
        print(topic)
    return

def topic_exists(topic_name):
    '''return True if a topic with this name exists and False otherwise'''
    return MONGO_DB['topics'].find_one({'_id': topic_name}) != None

def create_topic():
    '''create a new topic, unless it already exists'''
    questions = [
        {
            'type': 'input',
            'name': 'topic_name',
            'message': 'Topic name',
        },
    ]
    answers = PyInquirer.prompt(questions)
    topic_name = answers['topic_name']
    if topic_exists(topic_name):
        print('A topic with that name already exists')
        return False
    MONGO_DB['topics'].insert_one({'_id': topic_name, 'papers': list(), 'references': list()})
    print(f'Created new topic {topic_name}')
    return True

def select_topic():
    '''select an existing topic'''
    topics = get_topics()
    if len(topics) == 0:
        print('There are no stored topics')
        return None
    topics.append('cancel')
    questions = [
        {
            'type': 'list',
            'name': 'topic_name',
            'message': 'Select a topic',
            'choices': topics,
        },
    ]
    answers = PyInquirer.prompt(questions)
    return answers['topic_name']

def delete_topic():
    '''delete an existing topic'''
    topic_name = select_topic()
    if topic_name is None or topic_name == 'cancel':
        return
    if not topic_exists(topic_name):
        print('A topic with that name doesn\'t exist')
        return
    MONGO_DB['topics'].delete_one({'_id': topic_name})
    print(f'Deleted topic {topic_name}')
    return

def query_paper_ids():
    '''query the user for paper ids'''
    questions = [
        {
            'type': 'editor',
            'name': 'paper_ids',
            'message': 'Add one paper ID per line',
        }
    ]
    answers = PyInquirer.prompt(questions)
    paper_ids = [paper_id.strip() for paper_id in answers['paper_ids'].split('\n')]
    return [paper_id for paper_id in paper_ids if len(paper_id)]

def add_papers_to_topic(topic):
    '''add multiple papers to a topic'''
    paper_ids = query_paper_ids()
    print('Adding papers:')
    papers = set(topic['papers'])
    for paper_id in paper_ids:
        try:
            paper = paper_from_paperid(paper_id)
            if paper is None:
                print(f'\t{paper_id} not found')
            else:
                paper_title = paper['title']
                print(f'\t{paper_id} ({paper_title}) found')
                papers.add(paper_id)
        except Exception as err:
            print(f'\t{paper_id} failed: {err}')
            continue
    topic['papers'] = list(papers)
    return

def print_topic_papers(topic):
    '''print the papers on a topic'''
    print('Papers:')
    print()
    paper_ids = topic['papers']
    papers = sorted([paper_from_paperid(paper_id) for paper_id in topic['papers']], key=lambda x: x['title'])
    for paper in papers:
        print(paper['title'])
        print('\t', [dct['name'].strip() for dct in paper['authors']])
        print()
    return

def print_topic_references(topic):
    '''print the external references of a topic'''
    print('External references on this topic include:')
    paper_ids = topic['references']
    for paper_id in paper_ids:
        paper = paper_from_paperid(paper_id)
        print(paper['title'], 'by', paper['authors'])
    return

def adjacent_paperids(paper_ids):
    '''return an iterator over the papers adjacent the given paper ids'''
    for paper_id in paper_ids:
        paper = paper_from_paperid(paper_id)
        for reference in paper['references']:
            if reference['paperId'] not in paper_ids:
                yield reference['paperId']
        for citation in paper['citations']:
            if citation['paperId'] not in paper_ids:
                yield citation['paperId']
    return

def topic_connection_fraction(papers, paper):
    '''return the fraction of connections between the given paper and set
    of papers.

    '''
    rv = sum((reference['paperId'] in papers for reference in paper['references']))
    rv += sum((citation['paperId'] in papers for citation in paper['citations']))
    rv /= len(paper['references']) + len(paper['citations'])
    return rv

def remove_papers_from_topic(topic):
    '''interactively remove papers from the topic'''
    papers = [paper_from_paperid(paper_id) for paper_id in topic['papers']]
    choices = sorted([paper['title'] for paper in papers])
    paperid_from_title = {paper['title']: paper['paperId'] for paper in papers}
    questions = [
        {
            'type': 'checkbox',
            'message': 'Select papers to remove from the topic',
            'choices': choices,
        },
    ]
    answers = PyInquirer.prompt(questions)
    selected_ids = {paperid_from_title[choice] for choice in answers['choices']}
    topic['papers'] = list(set(topic['papers']) - selected_ids)
    return

def edges_from_paperids(paper_ids):
    '''Return an iterator over the edges (corresponding to citations)
    adjacent to papers with the given IDs. Each edge is represented by
    a tuple (id of citing paper, id of reference).

    '''
    for paper_id in paper_ids:
        paper = paper_from_paperid(paper_id)
        for reference in paper['references']:
            yield (paper['paperId'], reference['paperId'])
        for citation in paper['citations']:
            yield (citation['paperId'], paper['paperId'])
    return

def citegraph_from_paperids(paper_ids, G=None):
    '''return the citation graph of papers on and adjacent to the topic.'''
    if G is None:
        G = nx.DiGraph()
    G.add_edges_from(edges_from_paperids(paper_ids))
    papers = [paper_from_paperid(paper_id) for paper_id in G.nodes()]
    papers = [paper for paper in papers if paper is not None]
    nx.set_node_attributes(G, {
        paper['paperId']: paper for paper in papers
        if 'title' in paper and 'paperId' in paper
    })
    return G

def position_nodes(G, name='position'):
    '''compute 2D position for nodes in the graph. positions are stored as
    node attributes with the given name.

    '''
    nx.set_node_attributes(G, nx.spring_layout(G), name=name)
    return G

def pagerank(G, name='rank'):
    '''compute PageRank for the graph. rank is stored as node attributes
    with the given name.

    '''
    nx.set_node_attributes(G, nx.pagerank(G), name=name)
    return G

def topic_cocitations(G, topic_ids, name='cocitations'):
    '''compute cocitations between the topic and all papers in the
    graph. is stored as node attributes with the given name.

    '''
    topic_citation_ids = set()
    for paper_id in topic_ids:
        paper = paper_from_paperid(paper_id)
        for citation in paper['citations']:
            topic_citation_ids.add(citation['paperId'])
    attrs = dict()
    for paper_id in G.nodes():
        paper = paper_from_paperid(paper_id)
        if paper is not None and 'citations' in paper:
            cocitations = sum(citation['paperId'] in topic_citation_ids for citation in paper['citations']) / (len(paper['citations']) + 1)
        else:
            cotiations = 0
        attrs[paper_id] = cocitations
    nx.set_node_attributes(G, attrs, name=name)
    return G

def ui_rank_topic(topic, include_topic=True, include_adjacent=False):
    '''rank papers on the topic by PageRank score.'''
    G = citegraph_from_paperids(topic['papers'])
    pagerank(G)
    if include_topic and include_adjacent:
        paper_ids = list(G.nodes())
    elif include_topic:
        paper_ids = [paper_id for paper_id in topic['papers'] if G.has_node(paper_id)]
    elif include_adjacent:
        paper_ids = set(G.nodes()) - set(topic['papers'])
    else:
        raise ValueError('at least one of include_topic and include_adjacent must be True.')

    paper_ids = sorted(paper_ids, key=lambda node: G.nodes[node]['rank'], reverse=True)
    for paper_id in paper_ids:
        paper = paper_from_paperid(paper_id)
        pr = G.nodes[paper_id]['rank']
        if 'title' in paper:
            print(paper['title'])
        else:
            print('UNKNOWN TITLE')
        if 'authors' in paper:
            print('\t', [dct['name'].strip() for dct in paper['authors']])
        else:
            print('UNKNOWN AUTHORS')
        print('\t', pr)
        print()

def ui_papers_from_paperids(paper_ids):
    '''return an iterator over the papers with given papers IDs. prints
    the outcome of each query (found/not found/error).

    '''
    for paper_id in paper_ids:
        try:
            paper = paper_from_paperid(paper_id)
            if paper is None:
                print(f'\t{paper_id} not found')
                continue
            assert paper['paperId'] == paper_id
            paper_title = paper['title']
            print(f'\t{paper_id} ({paper_title}) found')
            yield paper
        except Exception as err:
            print(f'\t{paper_id} failed: {err}')
    return

def topic_connectedness(topic_ids, paper):
    '''return a metric of how close to the topic the given paper is.'''
    refs_in_topic = sum((reference['paperId'] in topic_ids for reference in paper['references']))
    citations_in_topic = sum((citation['paperId'] in topic_ids for citation in paper['citations']))
    return refs_in_topic * citations_in_topic

def ui_discover_topic(topic):
    '''discover new papers on the topic'''
    topic_ids = set(topic['papers'])

    # find the set of papers that cite papers on the topic
    topic_citation_ids = set()
    for paper in ui_papers_from_paperids(topic_ids):
        for citation in paper['citations']:
            topic_citation_ids.add(citation['paperId'])

    # compute co-citation score for all papers adjacent to the topic
    v = list()
    adjacent_ids = set(adjacent_paperids(topic_ids))
    for paper in ui_papers_from_paperids(adjacent_ids):
        if 'citations' not in paper or 'title' not in paper:
            continue
        cocitations = sum(citation['paperId'] in topic_citation_ids for citation in paper['citations']) / (len(paper['citations']) + 1)
        connected = int(topic_connectedness(topic_ids, paper) > 0)
        v.append((paper['paperId'], paper['title'], connected, cocitations))

    # sort v by if it is connected and then by number of co-citations
    v = sorted(v, key=lambda x: x[3], reverse=True)
    v = sorted(v, key=lambda x: x[2], reverse=True)

    # the user indicates which papers to add to the topic
    choices = [{'name': f'[{connected}, {cocitations}] ' + title} for _, title, connected, cocitations in v]
    print(choices)
    paperid_from_choice = {choice['name']: paper_id for choice, (paper_id, _, _, _) in zip(choices, v)}
    questions = [
        {
            'type': 'checkbox',
            'name': 'choices',
            'message': 'Select papers to add to the topic',
            'choices': choices,
        },
    ]
    answers = PyInquirer.prompt(questions)
    print('--------')
    selected_ids = [paperid_from_choice[choice] for choice in answers['choices']]
    for paper_id in selected_ids:
        print('Adding:', paper_from_paperid(paper_id)['title'])
        topic_ids.add(paper_id)
    topic['papers'] = list(topic_ids)
    return

def topic_ui_loop():
    '''ui loop when selecting a specific topic'''
    topic_name = select_topic()
    if topic_name is None or topic_name == 'cancel':
        return
    topic = MONGO_DB['topics'].find_one({'_id': topic_name})
    if topic is None:
        print('A topic with that name doesn\'t exist')
        return
    while True:
        questions = [
            {
                'type': 'list',
                'name': 'action',
                'message': f'Select action for [{topic_name}]',
                'choices': [
                    'add papers',
                    'remove papers',
                    'discover papers',
                    'rank papers',
                    'rank adjacent papers',
                    'list papers',
                    'list references',
                    'show citation graph',
                    'save',
                    'exit'
                ],
            },
        ]
        answers = PyInquirer.prompt(questions)
        if answers['action'] == 'add papers':
            add_papers_to_topic(topic)
        elif answers['action'] == 'remove papers':
            remove_papers_from_topic(topic)
        elif answers['action'] == 'discover papers':
            ui_discover_topic(topic)
        elif answers['action'] == 'rank papers':
            ui_rank_topic(topic, include_topic=True, include_adjacent=False)
        elif answers['action'] == 'rank adjacent papers':
            ui_rank_topic(topic, include_topic=False, include_adjacent=True)
        elif answers['action'] == 'list papers':
            print_topic_papers(topic)
        elif answers['action'] == 'list references':
            print_topic_references(topic)
        elif answers['action'] == 'show citation graph':
            G = citegraph_from_paperids(topic['papers'])
            position_nodes(G)
            pagerank(G)
            topic_cocitations(G, topic['papers'])
            gui.plot_cite_graph(G)
        elif answers['action'] == 'save':
            MONGO_DB['topics'].replace_one({'_id': topic['_id']}, topic)
        elif answers['action'] == 'exit':
            return
        print()
    return

def ui_loop():
    '''main ui loop'''
    while True:
        questions = [
            {
                'type': 'list',
                'name': 'action',
                'message': 'Select action',
                'choices': [
                    'select topic',
                    'create topic',
                    'delete topic',
                    'list topics',
                    'exit',
                ],
            }
        ]
        answers = PyInquirer.prompt(questions)
        if answers['action'] == 'select topic':
            topic_ui_loop()
        elif answers['action'] == 'list topics':
            print_topics()
        elif answers['action'] == 'create topic':
            create_topic()
        elif answers['action'] == 'delete topic':
            delete_topic()
        elif answers['action'] == 'exit':
            return
        print()
    return

if __name__ == '__main__':
    ui_loop()
