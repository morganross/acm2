import paramiko

# Search both servers for React source files

servers = [
    ('16.145.206.59', 'WordPress Frontend'),
    ('54.71.183.56', 'Backend Server'),
]

for ip, name in servers:
    print(f"\n=== Searching {name} ({ip}) ===")
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username='backenddev', password='TempPass2026!', timeout=10)
        
        # Search for React/Vite project indicators
        commands = [
            'find /home -name "package.json" 2>/dev/null | head -20',
            'find /opt -name "package.json" 2>/dev/null | head -20', 
            'find /var -name "package.json" 2>/dev/null | head -20',
            'ls -la /home/backenddev/ 2>/dev/null',
        ]
        
        for cmd in commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode().strip()
            if output:
                print(f"\n$ {cmd}")
                print(output)
        
        ssh.close()
    except Exception as e:
        print(f"Error connecting to {ip}: {e}")
