# Client connection and connection related logic.

## Idea
Code in this subfolder should be self contained logic that can be used anywhere
else. Can be used as core with server connection functionality.

Expected content: Connection to server, getting information about server,
download updates, get settings, get projects and other entities, session
connection objects with changes tracker (transaction based).

It is expected that it is possible to connect to more then one server, even
if it probably won't be primary behavior. That means the implementation of
connection objects must not be singleton based.

Queried objects are represented as entities, objects that can be queried
dynamically when accessed. It is a questionable if that is usable in all cases
or we should have ability to use "pure data" in some cases. For example in UIs
or very specific queries are entities useless or much slower and it may be
harder to maintain entities during publishing.

??? Question implement this option as optional usage. It is maybe bigger chunk
for initial implementation then we may need.
It will have it's usage for project management syncrhonizations
    - e.g. ftrack -> OpenPype
