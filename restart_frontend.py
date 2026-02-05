import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# Use the ed25519 private key
key = paramiko.Ed25519Key.from_private_key_file('C:/Users/Administrator/.ssh/id_ed25519')
ssh.connect('16.145.206.59', username='bitnami', pkey=key)

stdin, stdout, stderr = ssh.exec_command('sudo /opt/bitnami/ctlscript.sh restart apache')
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err)
ssh.close()
print("Done!")
