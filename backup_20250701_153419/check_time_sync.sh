#!/bin/bash
echo "=== Time Synchronization Status ==="
chronyc tracking
echo ""
echo "=== Time Sources ==="
chronyc sources -v
echo ""
echo "=== System Time ==="
timedatectl status