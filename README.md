# openpype4-client
Mockup of possible hierarchy of OpenPype4 client.

Client will contain only core functionality with global codebase.

## Addons concept
Each individual chunk of code should be separated into an AddOn. Addon can contain Host implementation or Module implementation. It is planned that addons may have dependency to other Addons and may have Python dependencies. It is highly recommended to not combine host and module into same addon if the functionality is not dependent on each other.

Module in some way enhance default behavior. In most of cases probably by implementing host plugins, tools actions or tools themselves.

Host should contain host implementation and all required code to use it. If there is some code which is common for multiple hosts/modules it can be extracted into separated module addon which should be added as addon dependency. For example communication with adobe DCC can be extracted into AdobeServer module which can be used by multiple hosts AfterEffects, Photoshop etc.

@JakubTrllo Addons Notes
- how to handle Python dependencies?
    - There are "common" dependencies "Python version specific" dependencies and host specific dependencies
    - Some dependencies require to be build for specific Python version (and platform specific)
        - They have to built somewhere probably for all pythons and they must be deployable to client
    - How to handle version control of dependencies for all addons?
        - Good example could be NumPy which may be required by more then one addon, but each addon will specify different version. How to handle those cases?
- will there be any "required" addons? (e.g. current webserver module)
- how will be addons deployed?
    - Maybe similar way like current OpenPype is. Using zip files but one zip == one addon and dependencies in different package prepared by server? We probably won't to avoid redownloading dependencies on change of single line in addon/s.
- will we require some predefined namespace of addon?
    - in OP3 are addons dynamically imported and stored under dynamic python module `openpype_modules` so it is possible to import any code of module using `from openpype_modules.<module name> import ...`
    - most of community don't like this approach because IDE's don't like import from dynamic modules but at the same time having for example module name `ftrack` which would make import shorter `from ftrack import ...` but at the same time it is dangerous to have such a generic name in sys modules

## What should client contain/support?
- Connection to server
    - Connection to multiple servers?
    - If yes how to handle different client versions? (possible builds...)
         - Install builds by versions (similar to blender)
    - How to store local data for different servers e.g. addons, python dependencies etc.?
- Which code will be part of installation and addons
    - Most of the code will be addons.
- Base classes for addons, host implementation, module implementation.
- Pipeline related logic
- Tools used in host or on client side

## Current context handling in host
- right now current context is defined by project, asset and task (project, folder, task)
- how to handle them in code? right now they're handled using environment variables `legacy_io.Session` with keys `AVALON_PROJECT`, `AVALON_ASSET` and `AVALON_TASK`. I would preffer to use environment variables only as initial values for current context but don't change it afterwards (also not use). There should be single access to current context ideally part of host implementation so there is single access to it. Similarly should be handled registered host related plugins. Avoid singletons as much as possible. They're too dangerous, hard to maintain and document.
- What will define initial values of process context? Suggesting Project name, Folder id and Task id which are used on process start to create "context object" which would also give access to folder name, type and task name, type + other possible things? Context object should handle changes of them (e.g. when folder changes then task should be "unset" because it is not the same parent).


## 5.9.2022 Meeting Notes
- host and modules are both considered as Addons
    - module is some logic that don't have host implementation
    - host is implementation of dcc can be related to multiple DCCs (e.g. Nuke + Nuke X)
- addons are individual parts of code
    - "zip files" when downloaded which are versioned
    - addons probably won't be in built client application but default implementation will be available as separated repositories
- server will care about providing these files and about telling which will be used
    - we have to find out how to discover them
- pip could be used to deploy dependencies
    - pip can download from custom server (OpenPype server)
- a lot of addon code won't be part of client application but part of server so we don't have to handle so much as in v3
    - for example settings won't be part of addon on client side
- we've decided that addons won't be imported dynamically but path to their python package will be added to sys.path (and PYTHONPATH) on start
    - this requires that they must have unique "non common" name so they can be safely imported
    - for example 'ftrack' is too generic, instead of that should be used something like 'openpype_ftrack' (this won't be forced, just recommended)
    - we have to find out how to "discover" them, probably using server connection and knowing where are stored on the machine
- `openpype.lib` must contain only "ready to use" functions from any part of code
- abstract implementation of host will be moved from `openpype.pipeline` to `openpype.hosts`
- host will have 2 implementations public and in-dcc implementation
    - public is available from any part of code and must not contain any in DCC related code
    - in-dcc implementation can use any logic related to implementation itself
- public host interface is for methods and functionality that can be used before the application is launched
    - right now: workfile extensions and host specific environments that are not modifiable
- in-dcc implementation is access point to all current singletons and global functions
    - current context
    - registered plugins
    - workfile functions
    - load related functions
- there will be defined interfaces that will define which methods must be implemented for specific functionality
    - for example loading/creation require some methods
    - the interfaces should not be forced to be used as mixins but just as a place of definition what "developer" must implemend and how to make things work

## Tools
- How to define tools? Should tools be "Host tools" and "Standalone tools"?
- Not all tools we have now are UI tools. But all current non-UI tools can be converted into addons.
- Tools can be host specific how to "discover" them?
    - Should there be a dynamic way how to add host tools (using Addons)?
    - How to handle UI changes based on available/enabled AddOn?
        - e.g. SyncServer may not be available but at this moment is in core of Loader
- We should be prepared for "detached UI" (Logic and UI does not happen in same process)
    - This require to create some kind of communication between controller and UI (probably python 2 compatible)
    - Any part of UI must not use any calls to server but only to controller
        - Controller must have a model which will provide data so UI models can use them
    - Advantages:
        - Tool UI don't have to be running inside host
        - UI does not stuck when host have to do some logic
        - UI waiting does not stuck host
        - UI related callback that must happen during more then one dcc loop are doable (Blender implementation issues)
    - UI code should be separated from controller

## Applications
- How and where to define applications (dccs) and their hosts?
- There are applications that have host implementation (expected to be launched on task) and applications that don't have host and have custom launch actions (e.g. DJV, RV)
    - Application != Host but some applications require their implementation too because can't be launched on task (or it doesn't make sense)
- All of them may have icons, pre/post launch hooks
- Where to put implementation of applications on client side.
    - it requires system settings and local settings

RESULT: Logic will be moved to a pipeline package. There must be ability in Application settings to tell if application has host implementation (and which) and if can be executed on task.

## Settings
- How much should be settings handled on client side?
- Only part that would make sense to be handled on client side are "local settings" and local roots
    - this is connected to retrieving of representation path which is now "simple" in terms that the representation has single file or sequence but considering that representation could potentially have more then one file (resources) in that case loader should call some function which would return paths for the machine


### Dowloaded updates/addons/python packages on machine
In OP3 there is single zip file containing core functionality with modules and hosts. For v4 it is expected that core functionality will still be in some kind of zip but
modules and hosts will be maintained by their own zips.
```
--- Some dir in local data ---
|- openpype-v4.0.0.zip
|   |- openpype
|
|- adobe-server-v1.0.0.zip
|   |- openpype_adobe_server
|
|- ftrack-v1.3.2.zip
|   |- openpype_ftrack
|
|- ftrack-v1.3.3.zip
|   |- openpype_ftrack
|
|- photoshop-v1.0.0.zip
|   |- openpype_photoshop
|
|- photoshop-v1.0.0+staging.zip
|   |- openpype_photoshop
|
|- maya-v1.0.0.zip
|   |- openpype_maya
|
|- nuke-v1.0.0.zip
|   |- openpype_nuke
|
|- webserver-v1.0.0.zip
|   |- openpype_webserver
|
|- site-packages-windows-v1.0.0.zip
|   |- requests
|   |- six.py
|
|- site-packages-windows-v1.0.1.zip
|   |- requests
|   |- ftrack_api
|   |- six.py
|
|- ...
```
This is how I imagine the files will look like in reality on machine.
- Where this logic will be located?
