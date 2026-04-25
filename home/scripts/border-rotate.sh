#!/bin/bash

angle=0

while true; do
    hyprctl keyword general:col.active_border "rgba(00ffffff) rgba(ff00ffff) ${angle}deg"
    angle=$(( (angle + 5) % 360 ))
    sleep 0.05
done
