# GUI code

import plotly.graph_objects as go
import networkx as nx
import numpy as np

def plot_cite_graph(G, pos=None, size=None, color=None):
    '''plot the citation graph'''
    if len(G) == 0:
        print('graph is empty')
        return

    # get edge coordinates
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = G.nodes[edge[0]]['position']
        x1, y1 = G.nodes[edge[1]]['position']
        edge_x.append(x0)
        edge_x.append(x1)
        edge_x.append(None)
        edge_y.append(y0)
        edge_y.append(y1)
        edge_y.append(None)

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines')

    # get node coordinates
    node_x = []
    node_y = []
    for node in G.nodes():
        x, y = G.nodes[node]['position']
        node_x.append(x)
        node_y.append(y)

    # plot nodes and edges
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers',
        hoverinfo='text',
        marker=dict(
            showscale=True,
            # colorscale options
            #'Greys' | 'YlGnBu' | 'Greens' | 'YlOrRd' | 'Bluered' | 'RdBu' |
            #'Reds' | 'Blues' | 'Picnic' | 'Rainbow' | 'Portland' | 'Jet' |
            #'Hot' | 'Blackbody' | 'Earth' | 'Electric' | 'Viridis' |
            colorscale='YlGnBu',
            reversescale=True,
            color=[],
            size=10,
            colorbar=dict(
                thickness=15,
                title='Topic Cocitations',
                xanchor='left',
                titleside='right'
            ),
            line_width=2))

    # the area of each node is proportional to its rank
    node_ranks = np.fromiter((G.nodes[node]['rank'] for node in G.nodes()), dtype=float)
    node_sizes = 2*np.sqrt(node_ranks / np.pi)
    MIN_SIZE_PX = 10
    node_sizes *= MIN_SIZE_PX / node_sizes.min()
    node_trace.marker.size = node_sizes

    # the node color is computed from topic cocitations
    node_trace.marker.color = node_ranks = np.fromiter((G.nodes[node]['cocitations'] for node in G.nodes()), dtype=int)

    # paper title in mouse-over text
    node_text = list()
    for node in G.nodes():
        if 'title' in G.nodes[node]:
            node_text.append(G.nodes[node]['title'])
        else:
            node_text.append('')
    node_trace.text = node_text

    # create figure
    fig = go.Figure(
        data=[edge_trace, node_trace],
        layout=go.Layout(
            title='<br>Citation Graph',
            titlefont_size=16,
            showlegend=False,
            hovermode='closest',
            margin=dict(b=20,l=5,r=5,t=40),
            annotations=[ dict(
                text='',
                showarrow=False,
                xref="paper", yref="paper",
                x=0.005, y=-0.002 ) ],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
    )
    fig.show()
