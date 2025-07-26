# GPT-4o Realtime Voice Assistant Setup Guide

## Overview

The `05_VoiceBot_Realtime.py` file implements a sophisticated real-time voice assistant using Azure OpenAI's GPT-4o Realtime Preview API with WebRTC for ultra-low latency audio streaming.

## Features

- **Real-time Audio Streaming**: WebRTC integration for minimal latency
- **GPT-4o Realtime API**: Latest Azure OpenAI realtime model support
- **Voice Activity Detection**: Automatic speech detection and processing
- **Conversation Persistence**: Automatic saving to Cosmos DB
- **Customizable Voice Settings**: Multiple voice options and personality configurations
- **Advanced Audio Processing**: Echo cancellation, noise suppression, auto gain control

## Prerequisites

### 1. Azure OpenAI Setup

You need an Azure OpenAI resource with:
- **Region**: East US 2 or Sweden Central (required for Realtime API)
- **Model Deployment**: `gpt-4o-realtime-preview` or `gpt-4o-mini-realtime-preview`
- **API Version**: `2025-04-01-preview`

### 2. Environment Variables

Add these to your environment configuration:

```bash
# Azure OpenAI Realtime API
AZURE_OPENAI_REALTIME_DEPLOYMENT=gpt-4o-realtime-preview
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
```

### 3. Required Dependencies

Install the additional packages for WebRTC functionality:

```bash
# Install WebRTC dependencies
pip install streamlit-webrtc>=0.47.1
pip install pyav>=10.0.0
pip install websockets>=12.0
pip install aiofiles>=23.0.0

# Or install all at once
pip install -r requirements.txt
```

## Installation Steps

### Step 1: Update Dependencies

The `pyproject.toml` has been updated with the required packages. Install them:

```bash
cd src/backend
pip install -e .
```

### Step 2: Deploy Azure OpenAI Realtime Model

1. Go to Azure AI Studio or Azure Portal
2. Navigate to your Azure OpenAI resource
3. Deploy a `gpt-4o-realtime-preview` model
4. Note the deployment name and update your environment variables

### Step 3: Configure Environment

Ensure your environment variables include:

```bash
AZURE_OPENAI_ENDPOINT=https://your-eastus2-openai.openai.azure.com/
AZURE_OPENAI_REALTIME_DEPLOYMENT=your-realtime-deployment-name
```

### Step 4: Run the Application

```bash
streamlit run src/backend/pages/05_VoiceBot_Realtime.py
```

## Usage Guide

### Starting a Conversation

1. **Access the Page**: Navigate to "VoiceBot Realtime" in the sidebar
2. **Configure Settings**: Adjust voice, instructions, and sensitivity in the sidebar
3. **Click START**: Begin the WebRTC connection
4. **Start Speaking**: The AI will respond automatically when you pause

### Voice Settings

- **Voice Selection**: Choose from 10 different AI voices
- **Instructions**: Customize the AI's personality and behavior
- **VAD Sensitivity**: Adjust how sensitive the voice detection is
- **Silence Duration**: Control how long to wait before processing speech

### Advanced Features

- **Session Management**: Automatic conversation saving and loading
- **Real-time Status**: Live connection and API status indicators
- **Conversation History**: View and manage past conversations
- **Error Handling**: Robust error recovery and connection management

## Technical Architecture

### Audio Processing Pipeline

1. **WebRTC Input**: Captures audio from user's microphone
2. **Audio Processing**: Converts to PCM16, 24kHz, mono format
3. **WebSocket Streaming**: Sends audio chunks to Azure OpenAI Realtime API
4. **Real-time Response**: Receives and plays back AI response audio
5. **Conversation Logging**: Saves interactions to Cosmos DB

### Key Components

- **RealtimeAudioProcessor**: Handles WebRTC audio processing and API communication
- **RealtimeConfig**: Configuration object for API settings
- **WebSocket Client**: Manages connection to Azure OpenAI Realtime API
- **Audio Buffering**: Efficient audio data handling and streaming

## Troubleshooting

### Common Issues

**No Audio Input/Output**
- Check microphone permissions in browser
- Ensure WebRTC is supported (modern browsers only)
- Try refreshing the page and restarting the connection

**Connection Failures**
- Verify Azure OpenAI endpoint and deployment name
- Check that you're using a supported region (East US 2 or Sweden Central)
- Ensure API version is `2025-04-01-preview`

**Poor Audio Quality**
- Adjust VAD sensitivity settings
- Check network connection stability
- Ensure proper audio device configuration

**Package Installation Issues**
```bash
# For Windows users, may need additional setup for pyav
conda install av -c conda-forge

# Or use system package manager
# On Ubuntu/Debian:
sudo apt-get install libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libswresample-dev libavfilter-dev
```

### Debug Logging

Enable detailed logging by setting:

```bash
LOGLEVEL=DEBUG
LOGLEVEL_AZURE=DEBUG
```

## Performance Optimization

### Network Requirements

- **Minimum Bandwidth**: 64 kbps upload/download
- **Recommended**: 128+ kbps for optimal quality
- **Latency**: <100ms for best experience

### Browser Compatibility

- **Chrome/Edge**: Full support (recommended)
- **Firefox**: Supported with some limitations
- **Safari**: Basic support (may have audio issues)
- **Mobile Browsers**: Limited support

## Security Considerations

- **Authentication**: Uses Azure Managed Identity (recommended)
- **Encryption**: All audio data encrypted in transit
- **Privacy**: No audio data stored by default
- **CORS**: Properly configured for WebRTC

## API Costs

The Realtime API has different pricing than standard models:
- **Input Audio**: Charged per audio minute
- **Output Audio**: Charged per audio minute
- **Text Processing**: Standard token-based pricing

Monitor usage in Azure Cost Management.

## Future Enhancements

Planned improvements:
- **Function Calling**: Integration with custom tools and APIs
- **Multi-language Support**: Real-time translation capabilities
- **Voice Cloning**: Custom voice training options
- **Enhanced VAD**: Better speech detection algorithms
- **Mobile App**: Native mobile application support
