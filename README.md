# CiteGraph

CiteGraph is a tool that uses the [citation graph](https://en.wikipedia.org/wiki/Citation_graph) (provided by [semanticscholar.org](https://www.semanticscholar.org/)) to discover the most important scientific papers published on a given topic. The workflow of using CiteGraph is as follows:

1. Create a new topic, or select an existing one.
2. Manually add papers to the topic by entering their semanticscholar ID, which can be found from the URL field of the corresponding semanticscholar.org page. For example, the ID of [this paper](https://www.semanticscholar.org/paper/Bitcoin-%3A-A-Peer-to-Peer-Electronic-Cash-System-Nakamoto/ecdd0f2d494ea181792ed0eb40900a5d2786f9c4) is `ecdd0f2d494ea181792ed0eb40900a5d2786f9c4`. You must add at least 1 paper manually to bootstrap the system.
3. CiteGraph downloads the nodes of the citation graph adjacent to all papers currently part of the topic and ranks them by how similar they are to the papers currently part of the topic. You may add one or more papers from this list to the topic, and repeat this step as many times as you like.
4. Use CiteGraph to visualize the citation graph. The size of nodes is proportional to the importance of the corresponding paper, where importance is defined as the PageRank of the node. This visualization can be used to prioritize which papers to read.

## Setup and running

Before running CiteGraph, you need to install and run MongoDB; see installation instructions [here](https://docs.mongodb.com/manual/installation/). Execute the scripts `startdb.sh` and `stopdb.sh` to start and stop the MongoDB database, respectively.

```bash
./startdb.sh # starts the database
./stopdb.sh # stops the database
```

Next, create a Python [virtual environment](https://docs.python.org/3/tutorial/venv.html), install dependencies, and run CiteGraph using the following commands.

```bash
# Create a new virtual environment
python -m venv venv

# Activate the virtual environment
source ./venv/bin/activate

# Install dependencies
pip install --user -r requirements.txt

# Run the program
python main.py
```