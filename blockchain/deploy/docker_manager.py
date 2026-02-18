# blockchain/deploy/docker_manager.py

import subprocess
import time
import sys
import json

def build_image():
    """Builds the Docker image for our blockchain node"""
    print("[Manager] Building Docker image 'military-chain-node'...")
    try:
        subprocess.run(["docker", "build", "-t", "military-chain-node", "."], check=True)
        print("[Manager] Build successful.")
    except subprocess.CalledProcessError:
        print("[Error] Docker build failed. Make sure Docker Desktop is running.")
        sys.exit(1)

def deploy_network(num_nodes=3):
    """Spins up N nodes and connects them"""
    print(f"[Manager] Deploying network with {num_nodes} nodes...")
    
    # 1. Create a Docker Network (so nodes can talk)
    try:
        subprocess.run(["docker", "network", "create", "chain-net"], stderr=subprocess.DEVNULL)
    except:
        pass # Network might already exist

    containers = []
    base_port = 8000

    for i in range(1, num_nodes + 1):
        node_name = f"node-{i}"
        host_port = base_port + i  # Node 1 -> 8001, Node 2 -> 8002
        
        print(f"   -> Starting {node_name} on port {host_port}...")
        
        cmd = [
            "docker", "run", "-d",
            "--name", node_name,
            "--network", "chain-net",
            "-p", f"{host_port}:8000",
            "military-chain-node"
        ]
        
        # Stop existing container if it exists
        subprocess.run(["docker", "rm", "-f", node_name], stderr=subprocess.DEVNULL)
        
        # Run new container
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            container_id = result.stdout.strip()[:12]
            containers.append({"name": node_name, "id": container_id, "port": host_port})
            print(f"      Started (ID: {container_id})")
        else:
            print(f"      Failed: {result.stderr}")

    print("\n[Manager] Network Deployed Successfully!")
    print(json.dumps(containers, indent=2))
    print("\nYou can now access the nodes at:")
    for c in containers:
        print(f" - {c['name']}: http://localhost:{c['port']}/docs")

if __name__ == "__main__":
    # Ensure we are in the project root
    import os
    if not os.path.exists("blockchain"):
        print("Error: Please run this script from the project root directory.")
        sys.exit(1)
        
    build_image()
    deploy_network(num_nodes=3)