import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

cmd = """
cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin
echo "=== Git Remote ==="
sudo git remote -v

echo ""
echo "=== All branches ==="
sudo git branch -a

echo ""
echo "=== Check if there's a different branch with more code ==="
sudo git fetch --all 2>/dev/null
sudo git branch -r
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()
