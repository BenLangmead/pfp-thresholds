FROM ghcr.io/openai/codex-universal:latest

# Install build essentials and dependencies
RUN apt-get update && apt-get install -y \
    cmake \
    gcc-10 \
    g++-10 \
    git \
    make \
    python3-pip \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Set GCC 10 as the default compiler
RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-10 100 \
    --slave /usr/bin/g++ g++ /usr/bin/g++-10 \
    --slave /usr/bin/gcov gcov /usr/bin/gcov-10

# Install Python dependencies
RUN pip3 install --no-cache-dir --break-system-packages pydivsufsort

# Set working directory
WORKDIR /workspace

# Copy the project files
COPY . .

# Create build directory
RUN mkdir -p build

# Build the project
WORKDIR /workspace/build
RUN cmake .. && make

# Set the working directory back to the project root
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
