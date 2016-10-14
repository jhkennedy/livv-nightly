#!/bin/bash

echo
echo "Cloning CISM and LIVVkit into current directory."

if [ "$1" == "develop" ]
then
    # Clone CISM
    git clone https://github.com/ACME-Climate/cism-piscees.git cism
    # Clone LIVV
    git clone https://github.com/ACME-Climate/LIVV.git LIVVkit
else
    # Clone CISM
    git clone https://github.com/CISM/cism.git cism
    # Clone LIVV
    git clone https://github.com/LIVVkit/LIVVkit.git LIVVkit
fi

