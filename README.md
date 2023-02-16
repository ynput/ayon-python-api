# AYON server API
Python client for connection server. Client must be (at least for some time) Python 2 compatible because will be used in DCC that are "older".

AYON Python api should support connection to server with raw REST functions and prepared functionality for work with entities. Must not contain only functionality that can be used with core server functionality.

Module support singleton connection which is using `AYON_SERVER_URL` and `AYON_TOKEN` environment variables as source for connection. The singleton connection is using `ServerAPI` object. There can be created multiple connection to different server at one time, for that purpose use `ServerAPIBase` object. 

## TODOs
- Find more suitable name for objects of `ServerAPI` (right now is used `connection` or `con`)
- Add folder and task changes to operations
  - Entity hub should use operations to update folders and tasks 
- Add option to use machine id in connection
  