#!/bin/bash
# Setup script to allow Tailscale GUI to run switch commands without password prompts

echo "Setting up permissions for Tailscale GUI..."
echo ""

# Option 1: Set operator permissions (RECOMMENDED)
echo "Option 1: Setting operator permissions (allows tailscale commands without sudo)"
echo "Running: sudo tailscale set --operator=$USER"
sudo tailscale set --operator=$USER

if [ $? -eq 0 ]; then
    echo "✓ Operator permissions set successfully"
    echo "Restarting tailscaled service..."
    sudo systemctl restart tailscaled
    echo "✓ Service restarted"
    echo ""
    echo "Now tailscale switch should work without sudo!"
else
    echo "✗ Failed to set operator permissions"
    echo ""
    echo "Trying Option 2: Setting up passwordless sudo for tailscale switch..."
    
    # Option 2: Passwordless sudo for tailscale switch command
    SUDOERS_LINE="$USER ALL=(ALL) NOPASSWD: /usr/bin/tailscale switch *"
    
    if ! sudo grep -q "tailscale switch" /etc/sudoers.d/tailscale-gui 2>/dev/null; then
        echo "$SUDOERS_LINE" | sudo tee /etc/sudoers.d/tailscale-gui > /dev/null
        sudo chmod 0440 /etc/sudoers.d/tailscale-gui
        echo "✓ Passwordless sudo configured for tailscale switch"
        echo "You can now run 'tailscale switch <nickname>' without entering password"
    else
        echo "✓ Passwordless sudo already configured"
    fi
fi

echo ""
echo "Setup complete! Try running the app again."

