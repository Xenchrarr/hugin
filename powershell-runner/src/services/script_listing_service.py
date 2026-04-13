import os
import re

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'scripts')

_PARAM_BLOCK_RE = re.compile(
    r'^\s*param\s*\((.*?)\)',
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)

_SINGLE_PARAM_RE = re.compile(
    r'\[(?P<type>(?:[^\[\]]|\[[^\]]*\])*)\]\s*\$(?P<name>\w+)'
    r'(?:\s*=\s*(?P<default>[^,\)]+))?',
    re.IGNORECASE,
)


def _parse_params(script_path):
    """Parse the top-level param() block of a .ps1 file."""
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read(4096)  # params are always at the top

    match = _PARAM_BLOCK_RE.search(content)
    if not match:
        return []

    block = match.group(1)
    params = []
    for m in _SINGLE_PARAM_RE.finditer(block):
        raw_type = m.group('type').strip()
        name = m.group('name').strip()
        default = m.group('default').strip() if m.group('default') else None

        # Skip ManualRun – always set to $false by the runner
        if name.lower() == 'manualrun':
            continue

        param_type = 'string'
        if 'boolean' in raw_type.lower() or 'bool' in raw_type.lower():
            param_type = 'boolean'

        if default is not None:
            default = default.strip().rstrip(',')
            if default in ('""', "''"):
                default = ''
            elif default.lower() in ('$true', '$false'):
                default = default.lower() == '$true'
            elif default.lower() == '$null':
                default = None

        params.append({
            'name': name,
            'type': param_type,
            'default': default,
        })

    return params


class ScriptListingService:
    def list_scripts(self, folder):
        """Return a list of scripts with their parameters for a given sub-folder."""
        target_dir = os.path.normpath(os.path.join(SCRIPTS_DIR, folder))
        if not target_dir.startswith(os.path.normpath(SCRIPTS_DIR)):
            raise ValueError('Invalid folder path')

        if not os.path.isdir(target_dir):
            raise FileNotFoundError(f'Folder not found: {folder}')

        scripts = []
        for filename in sorted(os.listdir(target_dir)):
            if not filename.endswith('.ps1'):
                continue

            full_path = os.path.join(target_dir, filename)
            relative_path = os.path.join(folder, filename)

            scripts.append({
                'name': filename,
                'path': relative_path,
                'params': _parse_params(full_path),
            })

        return scripts
