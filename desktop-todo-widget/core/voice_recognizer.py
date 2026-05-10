"""Voice recognition: Vosk offline, Google online, Windows SAPI system engines."""
import json as json_mod
import os
import subprocess
import sys
from datetime import datetime

from utils.common_utils import BASE_DIR, DATA_DIR, FROZEN

VOICE_LOG_FILE = os.path.join(DATA_DIR, "_voice_error.log")
VOICE_DEBUG_WAV = os.path.join(DATA_DIR, "_voice_debug.wav")


def voice_log(msg):
    """Append a timestamped message to the voice error log."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(VOICE_LOG_FILE), exist_ok=True)
        with open(VOICE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (ts, msg))
    except Exception:
        pass


def find_vosk_model():
    """Find Vosk CN model directory. Checks multiple locations for frozen exe support."""
    candidates = []
    candidates.append(os.path.expanduser("~/.vosk-model-cn"))
    candidates.append(os.path.join(BASE_DIR, "vosk-model-cn"))
    if FROZEN:
        if hasattr(sys, '_MEIPASS'):
            candidates.append(os.path.join(sys._MEIPASS, "vosk-model-cn"))
        candidates.append(os.path.join(os.path.dirname(sys.executable), "vosk-model-cn"))
    for p in candidates:
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "am", "final.mdl")):
            return p
    for p in candidates:
        if os.path.isdir(p):
            return p
    return None


class VoiceRecognizer:
    """Pure voice recognition engines — no UI dependencies."""

    @staticmethod
    def capture_audio(rate, stop_event, errors):
        """Capture audio from microphone. Returns raw PCM bytes or None."""
        frames = []
        p = None
        stream = None

        try:
            import pyaudio
            CHUNK = 1024
            FORMAT = pyaudio.paInt16
            CHANNELS = 1

            p = pyaudio.PyAudio()
            stream = p.open(format=FORMAT, channels=CHANNELS, rate=rate,
                           input=True, frames_per_buffer=CHUNK)
            while not stop_event.is_set():
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
        except ImportError:
            msg = "[录音] PyAudio 未安装，请运行: pip install PyAudio"
            errors.append(msg)
            voice_log(msg)
            return None
        except OSError as e:
            err_msg = str(e)
            if "No Default Input Device" in err_msg or "Device unavailable" in err_msg:
                full_msg = "[录音] 未检测到麦克风设备，请检查麦克风是否已连接"
            elif "9999" in err_msg or "Unanticipated host error" in err_msg:
                full_msg = "[录音] 音频设备被占用或不可用"
            else:
                full_msg = "[录音] 音频设备错误: %s" % err_msg
            errors.append(full_msg)
            voice_log(full_msg)
            voice_log("  PyAudio OSError 详情: %s" % e)
            return None
        except Exception as e:
            full_msg = "[录音] 音频初始化失败: %s" % e
            errors.append(full_msg)
            voice_log(full_msg)
            return None
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if p:
                try:
                    p.terminate()
                except Exception:
                    pass

        if not frames:
            errors.append("[录音] 未采集到音频帧，请检查麦克风权限")
            return None

        print("[语音] 录音结束，采集 %d 帧" % len(frames))
        return b''.join(frames)

    @staticmethod
    def recognize_vosk(raw_data, rate, errors):
        """Recognize speech using Vosk offline engine. Returns text or None."""
        try:
            import vosk
        except ImportError:
            msg = "[离线Vosk] 库未安装，请运行: pip install vosk"
            errors.append(msg)
            voice_log(msg)
            return None

        model_path = find_vosk_model()
        if not model_path:
            msg = (
                "[离线Vosk] 中文模型未找到。\n"
                "  下载地址: https://alphacephei.com/vosk/models\n"
                "  下载 vosk-model-small-cn-0.22 并解压到以下任一位置:\n"
                "    • ~/.vosk-model-cn\n"
                "    • %s\\vosk-model-cn\n" % BASE_DIR
            )
            errors.append(msg)
            voice_log("Vosk 模型未找到 (搜索路径: %s, frozen=%s)" % (BASE_DIR, FROZEN))
            return None

        voice_log("Vosk 模型路径: %s" % model_path)
        try:
            model = vosk.Model(model_path)
            rec = vosk.KaldiRecognizer(model, rate)
            rec.SetWords(True)
        except Exception as e:
            msg = "[离线Vosk] 模型加载失败 (路径: %s): %s" % (model_path, e)
            errors.append(msg)
            voice_log(msg)
            return None

        chunk_size = 4000
        total = len(raw_data)
        for start in range(0, total, chunk_size):
            end = min(start + chunk_size, total)
            rec.AcceptWaveform(raw_data[start:end])

        try:
            result = json_mod.loads(rec.FinalResult())
            text = result.get("text", "").strip()
        except Exception:
            text = ""

        print("[语音] Vosk 识别结果: '%s'" % text)
        if text:
            return text.replace(" ", "")
        return None

    @staticmethod
    def recognize_sapi(errors):
        """Windows built-in Speech API via PowerShell (records AND recognizes).
        No external dependencies - uses System.Speech built into Windows 10/11."""
        if sys.platform != "win32":
            return None
        voice_log("启动 SAPI (PowerShell/System.Speech)...")
        try:
            ps_script = (
                "Add-Type -AssemblyName System.Speech\n"
                "try {\n"
                '  $culture = [System.Globalization.CultureInfo]::GetCultureInfo("zh-CN")\n'
                "} catch { exit 1 }\n"
                "$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)\n"
                "$dictation = New-Object System.Speech.Recognition.DictationGrammar\n"
                "$engine.LoadGrammar($dictation)\n"
                "try {\n"
                "  $engine.SetInputToDefaultAudioDevice()\n"
                "} catch { exit 2 }\n"
                '$result = $engine.Recognize([TimeSpan]::FromSeconds(8))\n'
                "if ($result) { $result.Text } else { '' }"
            )
            CREATE_NO_WINDOW = 0x08000000 if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=15,
                stdin=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
            text = proc.stdout.strip()
            voice_log("SAPI 返回: rc=%s, stderr='%s', text='%s'" % (
                proc.returncode, proc.stderr.strip()[:200], text))
            print("[语音] Windows SAPI 识别结果: '%s' (rc=%s)" % (text, proc.returncode))
            if proc.returncode == 1:
                errors.append("[系统SAPI] 系统未安装中文语音识别语言包")
                voice_log("SAPI 失败: 无中文语言包 (rc=1)")
            elif proc.returncode == 2:
                errors.append("[系统SAPI] 无法访问麦克风设备")
                voice_log("SAPI 失败: 麦克风访问失败 (rc=2)")
            elif text:
                return text.replace(" ", "")
            else:
                errors.append("[系统SAPI] 未识别到语音内容（8秒内未检测到说话）")
                voice_log("SAPI 返回空文本")
        except FileNotFoundError:
            msg = "[系统SAPI] PowerShell 不可用"
            errors.append(msg)
            voice_log("SAPI 失败: %s" % msg)
        except subprocess.TimeoutExpired:
            msg = "[系统SAPI] 识别超时（15秒内未返回结果）"
            errors.append(msg)
            voice_log("SAPI 失败: %s" % msg)
        except OSError as e:
            msg = "[系统SAPI] 系统错误: %s" % e
            errors.append(msg)
            voice_log("SAPI 失败: %s" % msg)
        return None

    @staticmethod
    def recognize_google(raw_data, rate, errors):
        """Recognize speech using Google online API. Returns text or None."""
        try:
            import speech_recognition as sr
        except ImportError:
            msg = "[在线] speech_recognition 未安装"
            errors.append(msg)
            voice_log(msg)
            return None

        try:
            recognizer = sr.Recognizer()
            audio_data = sr.AudioData(raw_data, rate, 2)
            print("[语音] 尝试 Google 识别...")
            voice_log("尝试 Google 在线识别...")
            text = recognizer.recognize_google(audio_data, language="zh-CN")
            print("[语音] Google 识别结果: %s" % text)
            voice_log("Google 识别成功: '%s'" % text)
            return text
        except sr.UnknownValueError:
            msg = "[在线] Google 未识别到语音内容"
            errors.append(msg)
            voice_log(msg)
        except sr.RequestError as e:
            msg = "[在线] Google 服务不可用（中国大陆需科学上网）: %s" % e
            errors.append(msg)
            voice_log(msg)
        except Exception as e:
            msg = "[在线] Google 识别异常: %s" % e
            errors.append(msg)
            voice_log(msg)
        return None

    @staticmethod
    def save_debug_wav(raw_data, rate, channels, fmt):
        """Save recorded audio to a WAV file for debugging."""
        try:
            import wave
            os.makedirs(os.path.dirname(VOICE_DEBUG_WAV), exist_ok=True)
            with wave.open(VOICE_DEBUG_WAV, "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)
                wf.setframerate(rate)
                wf.writeframes(raw_data)
            print("[语音] 录音已保存: %s" % VOICE_DEBUG_WAV)
        except Exception:
            pass
