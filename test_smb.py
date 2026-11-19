from smbprotocol.connection import Connection
from smbprotocol.session import Session
from smbprotocol.open import Open, CreateDisposition, FileAttributes, ShareAccess, ImpersonationLevel
import os

conn = Connection('100.113.214.74', 445)
conn.connect()
sess = Session(conn, 'Creb', '')
sess.connect()

print('Connected to session')
print('Session methods:', [m for m in dir(sess) if not m.startswith('_')])

# Try tree_connect via session
if hasattr(sess, 'tree_connect'):
    print('Has tree_connect')
    tree = sess.tree_connect('D$')
    print('Connected to tree D$')
elif hasattr(conn, 'tree_connect'):
    print('Has conn.tree_connect')
    tree = conn.tree_connect('D$')
    print('Connected to tree D$ via conn')
else:
    print('No tree_connect found')

sess.disconnect()
conn.disconnect()
