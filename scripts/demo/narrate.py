import sys, wave, io
from google import genai
from google.genai import types
V = sys.argv[1]
N = {
 "n1": "Last year, Malaysians lost more than two point seven billion ringgit to scams, and phone scams were the number one category. Most victims send the money themselves, while the scammer is still on the line. Blocklists can't help in that moment. Meet Kawal, Malay for guard: the AI that sits on the call with you.",
 "n2": "Here's a synthetic Macau scam call, in Bahasa Melayu. I put it on speaker and press start. Kawal streams the audio to Gemini three point eight Live, running on Cloud Run.",
 "n3": "Five scam tactics caught, from fake police to the safe account demand. Risk ninety eight, a full screen alert, and a spoken warning in Malay. On a genuine bank call, Kawal stays silent.",
 "n4": "Messages and screenshots go through a multi agent pipeline. Gemini three point eight Flash reads the content, while an evidence agent checks Google Search and Web Risk in parallel, and a community agent searches Firestore vector search. Seconds later: the verdict, the exact red flags, official sources, and the right hotline.",
 "n5": "Every check becomes redacted, real time intelligence for banks. Firestore clusters reports into campaigns. Gemini writes threat bulletins with concrete bank controls, and analysts can ask questions that are answered by tool calls over the data.",
 "n6": "Kawal runs on Cloud Run, Firestore, Firebase Hosting, Auth and App Check, and Gemini, all deployed with Terraform, with quotas and a budget kill switch keeping the bill near zero. Built in JAPAC, for the world.",
}
c = genai.Client(vertexai=True, project="japac-ai-builder-cup-26", location="global")
for k, text in N.items():
    r = c.models.generate_content(model="gemini-3.8-flash-tts", contents=text, config=types.GenerateContentConfig(
        response_modalities=["AUDIO"], speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")))))
    b = r.candidates[0].content.parts[0].inline_data
    data = b.data
    if b.mime_type != "audio/wav":
        buf = io.BytesIO(); w = wave.open(buf, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(data); w.close(); data = buf.getvalue()
    open(f"{V}/{k}.wav", "wb").write(data)
    w = wave.open(f"{V}/{k}.wav"); print(k, round(w.getnframes() / w.getframerate(), 1))
