import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

PLUGIN_DIR = '/bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin'

# Check if there's already a build from a previous run
commands = [
    f'ls -la {PLUGIN_DIR}/assets/react-build/',
    f'ls -la {PLUGIN_DIR}/assets/react-build/assets/ 2>/dev/null || echo "No assets subfolder"',
    f'cat {PLUGIN_DIR}/assets/react-build/index.html 2>/dev/null',
]

for cmd in commands:
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print(f"STDERR: {err}")

ssh.close()
