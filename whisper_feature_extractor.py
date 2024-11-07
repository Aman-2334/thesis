import os
import torch
import torchaudio
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from transformers import WhisperModel, WhisperProcessor

# Load Whisper model and processor
print("Loading Whisper model and processor...")
whisper_model = WhisperModel.from_pretrained('openai/whisper-base')
whisper_processor = WhisperProcessor.from_pretrained('openai/whisper-base')
print("Whisper model and processor loaded successfully.")

# ASVspoof2019 Dataset class for extracting Whisper features
class ASVspoofWhisperDataset(Dataset):
    def __init__(self, audio_dir, protocol_path, sampling_rate=16000, target_length=3000):
        self.audio_dir = audio_dir
        self.metadata = self.load_metadata(protocol_path)
        self.sampling_rate = sampling_rate
        self.target_length = target_length
        print(f"Dataset initialized with {len(self.metadata)} samples.")

    def load_metadata(self, protocol_path):
        data = []
        with open(protocol_path, 'r') as f:
            for line in f.readlines():
                parts = line.strip().split()
                filename = parts[1]  # Second column is the file name
                label = 0 if parts[4] == 'bonafide' else 1  # 'bonafide' is 0 (real), 'spoof' is 1
                data.append((filename, label))
        print("Metadata loaded successfully.")
        return data

    def __len__(self):
        return len(self.metadata)

    def __getitem__(self, idx):
        filename, label = self.metadata[idx]
        audio_path = os.path.join(self.audio_dir, filename + '.flac')
        
        # Load the audio file
        waveform, sample_rate = torchaudio.load(audio_path)
        print(f"Loaded audio file: {audio_path}")

        # Resample if needed
        if sample_rate != self.sampling_rate:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=self.sampling_rate)
            waveform = resampler(waveform)
            print(f"Resampled audio to {self.sampling_rate} Hz.")

        # Remove extra dimensions if needed
        waveform = waveform.squeeze(0)

        # Convert waveform to mel-spectrogram using Whisper processor
        mel_features = whisper_processor.feature_extractor(
            waveform,
            sampling_rate=self.sampling_rate,
            return_tensors="pt"
        ).input_features.squeeze(0)  # Remove batch dimension

        # Pad or truncate to target length
        if mel_features.size(-1) < self.target_length:
            padding = self.target_length - mel_features.size(-1)
            mel_features = F.pad(mel_features, (0, padding), mode='constant', value=0)
            print(f"Padded mel-spectrogram to length {self.target_length}.")
        else:
            mel_features = mel_features[:, :self.target_length]
            print(f"Truncated mel-spectrogram to length {self.target_length}.")

        return mel_features, label

# Define paths
audio_dir = 'dataset\\ASVspoof2019\\LA\\ASVspoof2019_LA_train\\flac'
# CSV or TXT with file paths and labels
metadata_path = 'dataset\\ASVspoof2019\\LA\\ASVspoof2019_LA_cm_protocols\\ASVspoof2019.LA.cm.train.trn.txt'

# Create the dataset and DataLoader
dataset = ASVspoofWhisperDataset(audio_dir, metadata_path)
dataloader = DataLoader(dataset, batch_size=32, shuffle=False)

# Extract features and inspect
print("Starting feature extraction...")
for batch_idx, (mel_features, labels) in enumerate(dataloader):
    print(f"Processing batch {batch_idx + 1}/{len(dataloader)}")

    with torch.no_grad():
        # Pass mel-spectrograms through Whisper model
        whisper_encoder_outputs = whisper_model.encoder(mel_features)
        whisper_features = whisper_encoder_outputs.last_hidden_state  # Extract last hidden state

    # Print shape of extracted features and labels to confirm
    print("Whisper encoder feature shape:", whisper_features.shape)  # [batch_size, seq_length, hidden_size]
    print("Labels:", labels)

print("Feature extraction completed.")
