Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile("c:\Users\srini\AMAP\scripts\agla.wav")
$synth.Speak("Agla")
$synth.Dispose()
Write-Host "Generated agla.wav"
