import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

# Check the very first commit - what was the original state
cmd = """
cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin
echo "=== Original components in first commit (101013b) ==="
sudo git ls-tree --name-only -r 101013b react-app/src/components/ 2>/dev/null || echo "No components folder in 101013b"

echo ""
echo "=== Try 941fc93 (Initial commit) ==="
sudo git ls-tree --name-only -r 941fc93 react-app/src/components/ 2>/dev/null || echo "No components folder"

echo ""
echo "=== What's in the root of react-app in earliest commits? ==="
sudo git ls-tree --name-only -r 941fc93 react-app/ 2>/dev/null | head -30
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()
