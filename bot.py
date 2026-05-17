import os
import re
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from youtube_transcript_api import YouTubeTranscriptApi as YTA  # تعديل الاستدعاء لتفادي الأخطاء
from moviepy.video.io.VideoFileClip import VideoFileClip
import google.generativeai as genai

# ---- إعداد المفاتيح والتوكنز ----
TELEGRAM_TOKEN = "8958984509:AAFVW28c57rqirLcU1ZAvmOAAHjfRzwkkNE"
GEMINI_API_KEY = "AIzaSyBcmKutklzphRYyWVTTWkGF92DEC-X36Ps" 

genai.configure(api_key=GEMINI_API_KEY)

# دالة للترحيب بالمستخدم
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في بوت أتمتة المحتوى! 🚀\n"
        "أرسل لي أي رابط فيديو من اليوتيوب، وسأقوم باستخراج أفضل لقطة منه وتجهيزها للتيك توك تلقائياً."
    )

# دالة معالجة الروابط والشغل الثقيل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    
    # التأكد أن المرسل هو رابط يوتيوب
    if "youtube.com" not in url and "youtu.be" not in url:
        await update.message.reply_text("❌ فضلاً، أرسل رابط فيديو يوتيوب صحيح.")
        return

    status_message = await update.message.reply_text("⏳ جاري بدء العمل.. استخراج النص وتحليل الفيديو...")

    try:
        # 1. استخراج الـ ID وجلب النص بالطريقة المضمونة
        video_id = url.split("v=")[1].split("&")[0] if "v=" in url else url.split("/")[-1]
        
        # جلب النص باستخدام الاختصار الجديد لتفادي مشكلة الـ type object
        transcript = YTA.get_transcript(video_id, languages=['ar', 'en'])
        
        formatted_transcript = ""
        for entry in transcript:
            formatted_transcript += f"[{entry['start']:.2f}s] {entry['text']}\n"

        await status_message.edit_text("🧠 جاري تحليل النص عبر الذكاء الاصطناعي لاختيار أفضل لقطة...")

        # 2. إرسال النص لـ Gemini لاختيار أفضل لقطة
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        اقرأ النص التالي لفيديو يوتيوب، وحدد أفضل جزء حماسي أو مفيد ومثير للاهتمام يصلح ليكون فيديو قصير على تيك توك.
        يجب أن تكون مدة المقطع بين 30 إلى 60 ثانية كحد أقصى.
        أعطني النتيجة بدقة بالصيغة التالية تماماً ولا تكتب أي كلام آخر:
        Start: [وقت البداية بالثواني فقط]
        End: [وقت النهاية بالثواني فقط]
        Title: [العنوان المقترح للتيك توك مع هاشتاقات]

        النص:
        {formatted_transcript}
        """
        
        response = model.generate_content(prompt)
        ai_output = response.text

        # استخراج الأوقات والعنوان من رد الذكاء الاصطناعي
        start_time = float(re.search(r"Start:\s*([\d.]+)", ai_output).group(1))
        end_time = float(re.search(r"End:\s*([\d.]+)", ai_output).group(1))
        tiktok_title = re.search(r"Title:\s*(.*)", ai_output).group(1)

        await status_message.edit_text(f"📥 جاري تحميل الفيديو الأصلي وقص اللقطة المحددة ({start_time}s إلى {end_time}s)...")

        # 3. تحميل الفيديو وقصه
        video_file = f"{video_id}.mp4"
        output_file = f"{video_id}_tiktok.mp4"
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
            'outtmpl': video_file,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # تقطيع الفيديو وتعديل الأبعاد للتيك توك (9:16)
        clip = VideoFileClip(video_file).subclip(start_time, end_time)
        
        # تحجيم الفيديو ليكون طولي (أخذ منتصف الشاشة)
        w, h = clip.size
        target_w = int(h * 9 / 16)
        crop_clip = clip.crop(x_center=w/2, width=target_w, height=h)
        
        crop_clip.write_videofile(output_file, codec="libx264", audio_codec="aac")

        await status_message.edit_text("📤 جاري إرسال الفيديو الجاهز إليك...")

        # 4. إرسال الفيديو النهائي للمستخدم
        with open(output_file, 'rb') as video:
            await update.message.reply_video(
                video=video,
                caption=f"🎬 **العنوان المقترح:**\n{tiktok_title}\n\n⏱️ اللقطة من {start_time} إلى {end_time} ثانية."
            )

        # تنظيف الملفات المؤقتة لتوفير المساحة بالسيرفر
        clip.close()
        crop_clip.close()
        os.remove(video_file)
        os.remove(output_file)
        await status_message.delete()

    except Exception as e:
        await status_message.edit_text(f"❌ حدث خطأ أثناء المعالجة: {e}")

# تشغيل البوت
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("⚡ البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
        
