# openpype4-client
Mockup of possible hierarchy of OpenPype4 client.


@JakubTrllo Notes
## Modules, Addons and Hosts
- all of these will probably work the same or similar way
    - Will there be difference in them?
- some hosts may have common code which could be deployed by different addon
    for example "Adobe core" addon could be "requirement" for "Photoshop" host addon
    - Requirements of addons
    - They should be probably handled on server side
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
    - most of community don't like this approach because IDE's don't like import from dynamic modules but at the same time having for example module name `ftrack` which would make import shorter `from ftrack import ...` but at the same time it is dangerous to have such a generic name in sys path
- host will be probably discovered as addons?
    - will they be deployed same way?

## What should client contain/support?
- Connection to server
    - Connection to multiple servers?
    - If yes how to handle different client versions? (possible builds...)
         - Install builds by versions (similar to blender)
    - How to store local data for different servers e.g. addons, python dependencies etc.?
- Which code will be part of installation and addons
    - Most of the code will be addons.


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
    - we have to find out how to "discover" them
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
