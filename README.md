# Agent Lab

This is a repo for exploring the main techniques that make agents work like tool use, memory, context, state and swarms.

# Structure

## Notebooks

Jupyter notebooks contain experimentation with langchain and langgraph modules. Core concepts are in standalone modules as follow:

### core_concepts
- agent_basics.ipynb --> basic building blocks of an agent using langchain's create_agent class
- tools.ipynb --> introduction to how to define and call tools in agents
- agent_memory.ipynb --> techniques for creating and managing agent memory starting with short term
- multimodal.ipynb --> exploring multimodal (image and audio) inputs to a LLM


### advanced_concepts
- mcp.ipynb --> notebook for connecting agents to the custom MCP server
- context_and_state.ipynb --> notebook for exploring how to configure and supply state to agents
- swarms.ipynb --> exploring the use of agent swarms (network of smaller, focused agents)
- multiagent_systems.ipynb --> notebook for learning the basics of mutliagent systems
- wedding_planner.ipynb --> application of advanced concepts to multi-agent system for planning a wedding

## src
- personal_chef.py --> first application of core concepts to create a personal chef agent
- personal_chef_deploy.py --> modified personal chef for deployment on langgraph
- custom_mcp_server.py --> custom MCP server for answering questions about langchain and langgraph
