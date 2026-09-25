Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile("c:\Users\srini\AMAP\scripts\next_step.wav")
$synth.Speak("Next step")
$synth.Dispose()
Write-Host "Generated next_step.wav"
