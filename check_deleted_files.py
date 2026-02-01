import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

# Check what files changed between first react build commit and now
cmd = """
cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin
echo "=== Files that were deleted or changed since 37e671d (Update react build) ==="
sudo git diff --name-status 37e671d HEAD -- react-app/src/
echo ""
echo "=== What components existed in 37e671d ==="
sudo git ls-tree --name-only -r 37e671d react-app/src/components/
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())
print(stderr.read().decode())
ssh.close()
