"""Create public API functions based on ServerAPI methods.

Public functions are created in '_api.py' file and imported in '__init_.py'.
The script reads the 'ServerAPI' class and creates functions with the same
signature and docstring in '_api.py' and '__init__.py' with new/removed
functions.

The script is executed by running 'python automated_api.py' in the terminal.

TODOs:
    Use same signature in api functions as is used in 'ServerAPI' methods.
        Right now is used only '(*args, **kwargs)' signature.
    Prepare CI or pre-commit hook to run the script automatically.
"""

import os
import sys
import re
import inspect
import typing

# Fake modules to avoid import errors

requests = type(sys)("requests")
requests.__dict__["Response"] = type(
    "Response", (), {"__module__": "requests"}
)

sys.modules["requests"] = requests
sys.modules["unidecode"] = type(sys)("unidecode")

import ayon_api  # noqa: E402
from ayon_api.server_api import ServerAPI, _PLACEHOLDER  # noqa: E402
from ayon_api.utils import NOT_SET  # noqa: E402

EXCLUDED_METHODS = {
    "get_default_service_username",
    "get_default_settings_variant",
    "validate_token",
    "set_token",
    "reset_token",
    "create_session",
    "close_session",
    "as_username",
    "validate_server_availability",
    "get_headers",
    "login",
    "logout",
    "set_default_service_username",
}
EXCLUDED_IMPORT_NAMES = {"GlobalContext"}
AUTOMATED_COMMENT = """
# ------------------------------------------------
#     This content is generated automatically.
# ------------------------------------------------
""".strip()


# Read init file and remove ._api imports
def prepare_init_without_api(init_filepath):
    with open(init_filepath, "r") as stream:
        content = stream.read()

    api_regex = re.compile(r"from \._api import \((?P<functions>[^\)]*)\)")
    api_imports = api_regex.search(content)
    start, end = api_imports.span()
    api_imports_text = content[start:end]
    functions_text = api_imports.group("functions")
    function_names = [
        line.strip().rstrip(",")
        for line in functions_text.split("\n")
        if line.strip()
    ]
    function_names_q = {
        f'"{name}"' for name in function_names
    }

    all_regex = re.compile(r"__all__ = \([^\)]*\)")
    all_content = all_regex.search(content)
    start, end = all_content.span()
    all_content_text = content[start:end]
    filtered_lines = []
    for line in content[start:end].split("\n"):
        found = False
        for name in function_names_q:
            if name in line:
                found = True
                break
        if not found:
            filtered_lines.append(line)
    new_all_content_text = (
        "\n".join(filtered_lines).rstrip(") \n") + "\n\n{all_content}\n)"
    )

    return (
        content
        .replace(api_imports_text, "{api_imports}")
        .replace(all_content_text, new_all_content_text)
    ).rstrip("\n")


# Creation of _api.py content
def indent_lines(src_str, indent=1):
    new_lines = []
    for line in src_str.split("\n"):
        if line:
            line = f"{'    ' * indent}{line}"
        new_lines.append(line)
    return "\n".join(new_lines)


def prepare_docstring(func):
    docstring = inspect.getdoc(func)
    if not docstring:
        return ""

    line_char = ""
    if "\n" in docstring:
        line_char = "\n"
    return f'"""{docstring}{line_char}\n"""'


def _get_typehint(annotation, api_globals):
    if inspect.isclass(annotation):
        module_name_parts = list(str(annotation.__module__).split("."))
        module_name_parts.append(annotation.__name__)
        module_name_parts.reverse()
        options = []
        _name = None
        for name in module_name_parts:
            if _name is None:
                _name = name
                options.append(name)
            else:
                _name = f"{name}.{_name}"
                options.append(_name)

        options.reverse()
        for option in options:
            try:
                # Test if typehint is valid for known '_api' content
                exec(f"_: {option} = None", api_globals)
                return option
            except NameError:
                pass

        typehint = options[0]
        print("Unknown typehint:", typehint)
        typehint = f'"{typehint}"'
        return typehint

    typehint = (
        str(annotation)
        .replace("NoneType", "None")
    )
    full_path_regex = re.compile(
        r"(?P<full>(?P<name>[a-zA-Z0-9_\.]+))"
    )
    for item in full_path_regex.finditer(str(typehint)):
        groups = item.groupdict()
        name = groups["name"].split(".")[-1]
        typehint = typehint.replace(groups["full"], name)

    forwardref_regex = re.compile(
        r"(?P<full>ForwardRef\('(?P<name>[a-zA-Z0-9]+)'\))"
    )
    for item in forwardref_regex.finditer(str(typehint)):
        groups = item.groupdict()
        name = groups["name"].split(".")[-1]
        typehint = typehint.replace(groups["full"], f'"{name}"')

    try:
        # Test if typehint is valid for known '_api' content
        exec(f"_: {typehint} = None", api_globals)
    except NameError:
        print("Unknown typehint:", typehint)
        typehint = f'"{typehint}"'
    return typehint


def _get_param_typehint(param, api_globals):
    if param.annotation is inspect.Parameter.empty:
        return None
    return _get_typehint(param.annotation, api_globals)


def _add_typehint(param_name, param, api_globals):
    typehint = _get_param_typehint(param, api_globals)
    if not typehint:
        return param_name
    return f"{param_name}: {typehint}"


def _kw_default_to_str(param_name, param, api_globals):
    if param.default is inspect.Parameter.empty:
        return _add_typehint(param_name, param, api_globals)

    default = param.default
    if default is _PLACEHOLDER:
        default = "_PLACEHOLDER"
    elif default is NOT_SET:
        default = "NOT_SET"
    elif (
        default is not None
        and not isinstance(default, (str, bool, int, float))
    ):
        raise TypeError("Unknown default value type")
    else:
        default = repr(default)
    typehint = _get_param_typehint(param, api_globals)
    if typehint:
        return f"{param_name}: {typehint} = {default}"
    return f"{param_name}={default}"


def sig_params_to_str(sig, param_names, api_globals, indent=0):
    pos_only = []
    pos_or_kw = []
    var_positional = None
    kw_only = []
    var_keyword = None
    for param_name in param_names:
        param = sig.parameters[param_name]
        if param.kind == inspect.Parameter.POSITIONAL_ONLY:
            pos_only.append((param_name, param))
        elif param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            pos_or_kw.append((param_name, param))
        elif param.kind == inspect.Parameter.VAR_POSITIONAL:
            var_positional = param_name
        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            kw_only.append((param_name, param))
        elif param.kind == inspect.Parameter.VAR_KEYWORD:
            var_keyword = param_name

    func_params = []
    body_params = []
    for param_name, param in pos_only:
        body_params.append(param_name)
        func_params.append(_add_typehint(param_name, param, api_globals))

    if pos_only:
        func_params.append("/")

    for param_name, param in pos_or_kw:
        body_params.append(f"{param_name}={param_name}")
        func_params.append(_kw_default_to_str(param_name, param, api_globals))

    if var_positional:
        body_params.append(f"*{var_positional}")
        func_params.append(f"*{var_positional}")

    elif kw_only:
        func_params.append("*")

    for param_name, param in kw_only:
        body_params.append(f"{param_name}={param_name}")
        func_params.append(_kw_default_to_str(param_name, param, api_globals))

    if var_keyword is not None:
        body_params.append(f"**{var_keyword}")
        func_params.append(f"**{var_keyword}")

    base_indent_str = " " * indent
    param_indent_str = " " * (indent + 4)

    func_params_str = "()"
    if func_params:
        lines_str = "\n".join([
            f"{param_indent_str}{line},"
            for line in func_params
        ])
        func_params_str = f"(\n{lines_str}\n{base_indent_str})"

    if sig.return_annotation is not inspect.Signature.empty:
        return_typehint = _get_typehint(sig.return_annotation, api_globals)
        func_params_str += f" -> {return_typehint}"

    body_params_str = "()"
    if body_params:
        lines_str = "\n".join([
            f"{param_indent_str}{line},"
            for line in body_params
        ])
        body_params_str = f"(\n{lines_str}\n{base_indent_str})"

    return func_params_str, body_params_str


def prepare_api_functions(api_globals):
    functions = []
    for attr_name, attr in ServerAPI.__dict__.items():
        if (
            attr_name.startswith("_")
            or attr_name in EXCLUDED_METHODS
            or not callable(attr)
        ):
            continue

        sig = inspect.signature(attr)
        param_names = list(sig.parameters)
        if inspect.isfunction(attr):
            param_names.pop(0)

        func_def_params, func_body_params = sig_params_to_str(
            sig, param_names, api_globals
        )

        func_def = f"def {attr_name}{func_def_params}:\n"

        func_body_parts = []
        docstring = prepare_docstring(attr)
        if docstring:
            func_body_parts.append(docstring)

        func_body_parts.extend([
            "con = get_server_api_connection()",
            f"return con.{attr_name}{func_body_params}",
        ])

        func_body = indent_lines("\n".join(func_body_parts))
        full_def = func_def + func_body
        functions.append(full_def)
    return "\n\n\n".join(functions)


def main():
    print("Creating public API functions based on ServerAPI methods")
    # TODO order methods in some order
    dirpath = os.path.dirname(os.path.dirname(
        os.path.abspath(ayon_api.__file__)
    ))
    ayon_api_root = os.path.join(dirpath, "ayon_api")
    init_filepath = os.path.join(ayon_api_root, "__init__.py")
    api_filepath = os.path.join(ayon_api_root, "_api.py")

    print("(1/5) Reading current content of '_api.py'")
    with open(api_filepath, "r") as stream:
        old_content = stream.read()

    parts = old_content.split(AUTOMATED_COMMENT)
    if len(parts) == 1:
        raise RuntimeError(
            "Automated comment not found in '_api.py'"
        )
    if len(parts) > 2:
        raise RuntimeError(
            "Automated comment found multiple times in '_api.py'"
        )

    print("(2/5) Parsing current '__init__.py' content")
    formatting_init_content = prepare_init_without_api(init_filepath)

    # Read content of first part of `_api.py` to get global variables
    # - disable type checking so imports done only during typechecking are
    #   not executed
    old_value = typing.TYPE_CHECKING
    typing.TYPE_CHECKING = False
    api_globals = {"__name__": "ayon_api._api"}
    exec(parts[0], api_globals)
    for attr_name in dir(__builtins__):
        api_globals[attr_name] = getattr(__builtins__, attr_name)
    typing.TYPE_CHECKING = old_value

    # print(api_globals)
    print("(3/5) Preparing functions body based on 'ServerAPI' class")
    result = prepare_api_functions(api_globals)

    print("(4/5) Store new functions body to '_api.py'")
    new_content = f"{parts[0]}{AUTOMATED_COMMENT}\n{result}"
    with open(api_filepath, "w") as stream:
        print(new_content, file=stream)

    # find all functions and classes available in '_api.py'
    func_regex = re.compile(r"^(def|class) (?P<name>[^\(]*)(\(|:).*")
    func_names = []
    for line in new_content.split("\n"):
        result = func_regex.search(line)
        if result:
            name = result.group("name")
            if name.startswith("_") or name in EXCLUDED_IMPORT_NAMES:
                continue
            func_names.append(name)

    print("(5/5) Updating imports in '__init__.py'")
    import_lines = ["from ._api import ("]
    for name in func_names:
        import_lines.append(f"    {name},")
    import_lines.append(")")

    all_lines = [
        f'    "{name}",'
        for name in func_names
    ]
    new_init_content = formatting_init_content.format(
        api_imports="\n".join(import_lines),
        all_content="\n".join(all_lines),
    )

    with open(init_filepath, "w") as stream:
        print(new_init_content, file=stream)

    print("Public API functions created successfully")


if __name__ == "__main__":
    main()
