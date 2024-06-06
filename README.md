# AYON server API
Python client for connection server. The client is using REST and GraphQl to communicate with server with `requests` module.

AYON Python api should support connection to server with raw REST functions and prepared functionality for work with entities. Must not contain only functionality that can be used with core server functionality.

Module support singleton connection which is using `AYON_SERVER_URL` and `AYON_API_KEY` environment variables as source for connection. The singleton connection is using `ServerAPI` object. There can be created multiple connection to different server at one time, for that purpose use `ServerAPIBase` object.

## Install
AYON python api is available on PyPi:

    pip install ayon-python-api

For development purposes you may follow [build](#build-wheel) guide to build and install custom wheels.


## Cloning the repository
Repository does not have submodules or special cases. Clone is simple as:

    git clone git@github.com:ynput/ayon-python-api.git


## Build wheel
For wheel build is required a `wheel` module from PyPi:

    pip install wheel

Open terminal and change directory to ayon-python-api repository and build wheel:

    cd <REPOSITORY ROOT>/ayon-python-api
    python setup.py sdist bdist_wheel   
    

Once finished a wheel should be created in `./dist/ayon_python_api-<VERSION>-py3-none-any`.

---

### Wheel installation
The wheel file can be used to install using pip:

    pip install <REPOSITORY ROOT>/dist/ayon_python_api-<VERSION>-py3-none-any

If pip complain that `ayon-python-api` is already installed just uninstall existing one first:
    
    pip uninstall ayon-python-api


## TODOs
- Find more suitable name of `ServerAPI` objects (right now is used `con` or `connection`)
- Add all available CRUD operation on entities using REST
- Add folder and task changes to operations
- Enhance entity hub
  - Missing docstrings in EntityHub -> especially entity arguments are missing
  - Better order of arguments for entity classes
    - Move entity hub to first place
    - Skip those which are invalid for the entity and fake it for base or remove it from base
  - Entity hub should use operations session to do changes
  - Entity hub could also handle 'product', 'version' and 'representation' entities
  - Missing 'status' on folders
  - Missing assignees on tasks
  - Pass docstrings and arguments definitions from `ServerAPI` methods to global functions
- Split `ServerAPI` into smaller chunks (somehow), the class has 4k+ lines of code
- Add .pyi stub for ServerAPI 
- Missing websockets connection
