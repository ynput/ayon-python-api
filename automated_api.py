import os
import inspect
import ayon_api
from ayon_api import ServerAPI

EXCLUDED_METHODS = {
    "get_default_service_username",
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
AUTOMATED_COMMENT = "\n".join((
    "# ------------------------------------------------",
    "#     This content is generated automatically.",
    "# ------------------------------------------------",
))

def indent_lines(src_str, indent=1):
    new_lines = []
    for line in src_str.split("\n"):
        if line:
            line = f"{'    ' * indent}{line}"
        new_lines.append(line)
    return "\n".join(new_lines)


def split_sig_str(sig_str):
    args_str = sig_str[1:-1]
    args = [f"    {arg.strip()}" for arg in args_str.split(",")]
    joined_args = ",\n".join(args)

    return f"(\n{joined_args}\n)"


def prepare_func_def_line(attr_name, sig_str):
    return f"def {attr_name}{sig_str}:\n"


def prepare_docstring(func):
    docstring = inspect.getdoc(func)
    if not docstring:
        return ""

    line_char = ""
    if "\n" in docstring:
        line_char = "\n"
    return f'"""{docstring}{line_char}\n"""'


def prapre_body_sig_str(sig_str):
    if "=" not in sig_str:
        return sig_str

    args_str = sig_str[1:-1]
    args = []
    for arg in args_str.split(","):
        arg = arg.strip()
        if "=" in arg:
            parts = arg.split("=")
            parts[1] = parts[0]
            arg = "=".join(parts)
        args.append(arg)
    joined_args = ", ".join(args)
    return f"({joined_args})"


def prepare_body_parts(attr_name, sig_str):
    output = [
        "con = get_server_api_connection()",
    ]
    body_sig_str = prapre_body_sig_str(sig_str)
    return_str = f"return con.{attr_name}{body_sig_str}"
    if len(return_str) + 4 <= 79:
        output.append(return_str)
        return output

    return_str = f"return con.{attr_name}{split_sig_str(body_sig_str)}"
    output.append(return_str)
    return output


def prepare_api_functions():
    functions = []
    for attr_name, attr in ServerAPI.__dict__.items():
        if (
            attr_name.startswith("_")
            or attr_name in EXCLUDED_METHODS
            or not callable(attr)
        ):
            continue

        sig = inspect.signature(attr)
        base_sig_str = str(sig)
        if base_sig_str == "(self)":
            sig_str = "()"
        else:
            sig_str = "(*args, **kwargs)"

        func_def = prepare_func_def_line(attr_name, sig_str)

        func_body_parts = []
        docstring = prepare_docstring(attr)
        if docstring:
            func_body_parts.append(docstring)

        func_body_parts.extend(prepare_body_parts(attr_name, sig_str))

        func_body = indent_lines("\n".join(func_body_parts))
        full_def = func_def + func_body
        functions.append(full_def)
    return "\n\n\n".join(functions)


def main():
    # TODO add other content in '_api.py'
    # TODO order methods in some order
    # TODO prepare '__init__.py' content too
    result = prepare_api_functions()
    dirpath = os.path.dirname(os.path.dirname(
        os.path.abspath(ayon_api.__file__)))
    filepath = os.path.join(dirpath, "ayon_api", "_api.py")
    with open(filepath, "r") as stream:
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

    new_content = f"{parts[0]}{AUTOMATED_COMMENT}\n{result}"
    with open(filepath, "w") as stream:
        print(new_content, file=stream)


if __name__ == "__main__":
    main()
