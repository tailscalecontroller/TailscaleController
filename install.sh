#!/bin/bash
# Installation script for Tailscale GUI

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Installing Tailscale GUI Controller..."

# Make script executable
chmod +x "$SCRIPT_DIR/tailscale_gui.py"

# Install desktop file
if [ -d "$HOME/.local/share/applications" ]; then
    # Create desktop file with correct path
    cat > "$HOME/.local/share/applications/tailscale-gui.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Tailscale Controller
Comment=Control Tailscale, switch accounts, and view devices
Exec=python3 $SCRIPT_DIR/tailscale_gui.py
Icon=network-workgroup
Terminal=false
Categories=Network;
Path=$SCRIPT_DIR
StartupNotify=true
EOF
    echo "Desktop file installed to ~/.local/share/applications/"
    update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
    echo "Desktop database updated"
else
    echo "Warning: ~/.local/share/applications/ not found. Desktop file not installed."
fi

echo ""
echo "Installation complete!"
echo ""
echo "To run the application:"
echo "  python3 $SCRIPT_DIR/tailscale_gui.py"
echo ""
echo "Or look for 'Tailscale Controller' in your application menu."

