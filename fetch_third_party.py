from smbprotocol.connection import Connection
from smbprotocol.session import Session
from smbprotocol.tree import Tree
from smbprotocol.open import Open, CreateDisposition, FileAttributes, ShareAccess, ImpersonationLevel
import os

# Connect to Tower SMB share
conn = Connection('100.113.214.74', 445)
conn.connect()

try:
    sess = Session(conn, 'Creb', '')
    sess.connect()
    tree = Tree(sess, 'D$')
    tree.connect()

    base_path = 'MITRE/goose/third_party'
    local_base = '/home/dev/snapshot/goose/third_party'

    def download_file(smb_path, local_path):
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        open_ = Open(tree, smb_path)
        open_.create(
            CreateDisposition.FILE_OPEN,
            FileAttributes.FILE_ATTRIBUTE_NORMAL,
            ShareAccess.FILE_SHARE_READ,
            ImpersonationLevel.Impersonation,
        )
        data = open_.read(0, 100_000_000)
        open_.close()
        with open(local_path, 'wb') as f:
            f.write(data['Buffer'])
        print(f'Downloaded: {smb_path} -> {local_path} ({len(data["Buffer"])} bytes)')

    def list_dir(smb_path):
        open_ = Open(tree, smb_path)
        open_.create(
            CreateDisposition.FILE_OPEN,
            FileAttributes.FILE_ATTRIBUTE_DIRECTORY,
            ShareAccess.FILE_SHARE_READ,
            ImpersonationLevel.Impersonation,
        )
        # Just query info to check existence
        open_.close()

    # Try to list third_party directory
    try:
        open_ = Open(tree, base_path)
        open_.create(
            CreateDisposition.FILE_OPEN,
            FileAttributes.FILE_ATTRIBUTE_DIRECTORY,
            ShareAccess.FILE_SHARE_READ,
            ImpersonationLevel.Impersonation,
        )
        print(f'Directory exists: {base_path}')
        # List files in the directory
        # SMB protocol doesn't easily list directories, let's try specific files
        open_.close()
    except Exception as e:
        print(f'Cannot list {base_path}: {e}')

    # Try specific files
    candidates = [
        ('cute_spirv/ckit.h', f'{local_base}/cute_spirv/ckit.h'),
        ('cute_spirv/cute_spirv.h', f'{local_base}/cute_spirv/cute_spirv.h'),
        ('cute_spirv/README.md', f'{local_base}/cute_spirv/README.md'),
        ('subprocess/subprocess.h', f'{local_base}/subprocess/subprocess.h'),
    ]

    for smb_rel, local_path in candidates:
        smb_path = f'{base_path}/{smb_rel}'
        try:
            download_file(smb_path, local_path)
        except Exception as e:
            print(f'Failed {smb_path}: {e}')

    tree.disconnect()
except Exception as e:
    print(f'Session error: {e}')
finally:
    conn.disconnect()
