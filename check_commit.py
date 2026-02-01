import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

# Check the diff - what was in the last few commits
cmd = """
cd /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin
sudo git show --stat e791806
"""

stdin, stdout, stderr = ssh.exec_command(cmd)
print("Latest commit (e791806):")
print(stdout.read().decode())
ssh.close()
