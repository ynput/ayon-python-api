# AYON server API
Python client for connection server. Client must be (at least for some time) Python 2 compatible because will be used in DCC that are "older".

AYON Python api should support connection to server with raw REST functions and prepared functionality for work with entities. Must not contain only functionality that can be used with core server functionality.

Module support singleton connection which is using `AYON_SERVER_URL` and `AYON_TOKEN` environment variables as source for connection. The singleton connection is using `ServerAPI` object. There can be created multiple connection to different server at one time, for that purpose use `ServerAPIBase` object. 

## TODOs
- Find more suitable name of `ServerAPI` objects (right now is used `con` or `connection`)
- Add all available CRUD operation on entities using REST
- Add folder and task changes to operations
- Enhance entity hub
  - Entity hub should use operations session to do changes
  - Entity hub could also handle 'subset', 'version' and 'representation' entities
  - Missing docstrings in EntityHub -> especially entity arguments are missing
- Pass docstrings and arguments definitions from `ServerAPI` methods to global functions
- Missing websockets connection