## Lib content
Lib should contain only ready to use functionality without other OpenPype
dependencies. That is primarily avoid recursive imports and also to avoid
put uncategorized code here. Imports of functionality must not raise errors
until the functionality is used so if is something only Python 3 compatible it
must not cause issues on Python 2 until it's called.
