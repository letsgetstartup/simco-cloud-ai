# SolidComAI

The premium, cross-platform mobile experience for Simco Manufacturing Intelligence.

## 🚀 Getting Started

This project is a **Flutter** application.

### Prerequisites
1.  Install the [Flutter SDK](https://docs.flutter.dev/get-started/install).
2.  Ensure you have an emulator running (Android or iOS) or a physical device connected.

### Setup & Run
Since this code was generated in a cloud environment, you need to initialize the platform-specific build files (Android/iOS/Web) on your machine.

1.  Open your terminal and navigate to this folder:
    ```bash
    cd solid_com_ai
    ```

2.  Initialize platform files:
    ```bash
    flutter create .
    ```

3.  Install dependencies:
    ```bash
    flutter pub get
    ```

5.  **Run the App**:
    ```bash
    flutter run
    ```

## 📱 Features
- **Premium Dark UI**: Designed with `GoogleFonts.outfit` and `GoogleFonts.inter`.
- **Secure Backend**: Connects directly to your Firebase Cloud Function (`https://solidcam-f58bc.web.app/ask`).
- **No API Key Required**: Fully automated using server-side secrets.
- **Markdown Support**: Renders rich text responses from Gemini 2.5 Pro.
