import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

PLUGIN_DIR = '/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin'

# Check git status and push if needed
commands = [
    f'sudo -u bitnami git -C {PLUGIN_DIR} status',
    f'sudo -u bitnami git -C {PLUGIN_DIR} push origin main',
]

for cmd in commands:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print(f"STDERR: {err}")

ssh.close()
