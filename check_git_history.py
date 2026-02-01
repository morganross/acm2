import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

cmd = """
cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin
sudo git config --global --add safe.directory /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin
sudo git log --oneline -30
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print("STDOUT:")
print(stdout.read().decode())
print("\nSTDERR:")
print(stderr.read().decode())
ssh.close()
