# Install build essentials and dependencies
apt-get update && apt-get install -y \
    cmake \
    gcc-10 \
    g++-10 \
    git \
    make \
    python3-pip \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Set GCC 10 as the default compiler
update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-10 100 \
    --slave /usr/bin/g++ g++ /usr/bin/g++-10 \
    --slave /usr/bin/gcov gcov /usr/bin/gcov-10

pip3 install --no-cache-dir --break-system-packages pydivsufsort

# Clone and build the project (adjust the repo URL as needed)
cd /workspace
git checkout -b build-options
mkdir -p build
cd build
cmake ..
make
