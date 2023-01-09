# AYON server API
Python client for connection server. Client must be (at least for some time) Python 2 compatible because will be used in DCC that are "older".

Client should support connection to server with raw REST functions and prepared functionality for work with entities. Must not contain only functionality that can be used with core server functionality.


## TODOs
- Current implementation contains prepared functions for entity queries which is not using full potential of OpenPype server but is MongoDB compatible.
    - only functions related to v4 should stay at that place and v3 compatible functions should be moved
- Missing settings getter
- Missing CRUD operations for entities (Only read is possible)
- More clear what is difference in `ServerAPIBase` and `ServerAPI`
    - `ServerAPI` was added primarily for desktop app which handle login and logout in a different way so the class should be maybe removed and `ServerAPIBase` should be renamed to `ServerAPI`
