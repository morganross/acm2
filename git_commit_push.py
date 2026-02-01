import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('16.145.206.59', username='backenddev', password='TempPass2026!')

commands = [
    # Configure git identity for bitnami user
    'sudo -u bitnami git config --global user.email "dev@acm2.local"',
    'sudo -u bitnami git config --global user.name "ACM2 Dev"',
    
    # Git commit
    'sudo -u bitnami git -C /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin commit -m "Add React UI source from backend repo"',
    
    # Git push
    'sudo -u bitnami git -C /bitnami/wordpress/wp-content/plugins/acm-wordpress-plugin push origin main',
]

for cmd in commands:
    print(f"\n{'='*60}")
    print(f"$ {cmd}")
    print('='*60)
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")

ssh.close()
print("\n\nDone!")
