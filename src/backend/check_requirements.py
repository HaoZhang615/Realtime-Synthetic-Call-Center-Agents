import os
import ast
import sys
from pathlib import Path

def get_imports_from_file(file_path):
    """Extract import statements from a Python file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        try:
            tree = ast.parse(file.read())
        except SyntaxError:
            print(f"Syntax error in file: {file_path}")
            return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                imports.add(name.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split('.')[0])
    return imports

def get_stdlib_modules():
    """Get a set of Python standard library module names."""
    return set(sys.stdlib_module_names)

def main():
    # Read current requirements.txt
    requirements_path = Path(__file__).parent / 'requirements.txt'
    with open(requirements_path, 'r') as f:
        requirements = {line.strip().split('==')[0].split('>=')[0] for line in f if line.strip() 
                       and not line.startswith('#')}

    # Get all Python files in src/backend
    backend_path = Path(__file__).parent
    py_files = list(backend_path.rglob('*.py'))

    # Collect all imports
    all_imports = set()
    for file in py_files:
        file_imports = get_imports_from_file(file)
        if file_imports:
            all_imports.update(file_imports)

    # Remove standard library modules
    stdlib_modules = get_stdlib_modules()
    third_party_imports = all_imports - stdlib_modules

    # Compare with requirements
    missing_requirements = third_party_imports - requirements
    unused_requirements = requirements - third_party_imports

    if missing_requirements:
        print("\nPotentially missing packages in requirements.txt:")
        for pkg in sorted(missing_requirements):
            print(f"- {pkg}")

    if unused_requirements:
        print("\nPotentially unused packages in requirements.txt:")
        for pkg in sorted(unused_requirements):
            print(f"- {pkg}")

    if not missing_requirements and not unused_requirements:
        print("\nAll requirements appear to be up to date!")

if __name__ == '__main__':
    main()