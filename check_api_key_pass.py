import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

# Check how WordPress passes API key to React app
cmd = 'cat /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin/admin/class-react-app.php | grep -A30 "wp_localize_script"'
print(f"$ {cmd}")
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
print(stdout.read().decode())

ssh.close()
