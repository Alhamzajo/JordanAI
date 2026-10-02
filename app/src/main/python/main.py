from facebook_parser import parse_facebook_posts
from reels_gen import generate_reels_concept

def process_facebook_data(html_file_path):
    print(f"🔄 جاري قراءة وتحليل الملف: {html_file_path} ...\n")
    
    posts = parse_facebook_posts(html_file_path)
    
    if not posts:
        print("⚠️ لم يتم العثور على منشورات أو أن المسار غير صحيح.")
        return

    print(f"✅ تم استخراج {len(posts)} منشور/منشورات بنجاح!\n")
    print("=" * 50)
    
    for index, post in enumerate(posts, start=1):
        print(f"📌 [المنشور رقم {index}]")
        print(f"📅 التاريخ: {post['timestamp']}")
        print(f"💬 النص: {post['content']}")
        
        visual, script = generate_reels_concept(post['content'])
        print(f"📸 زاوية التصوير المقترحة: {visual['angle']}")
        print(f"🎬 المشهد الأول في الريلز: {script['scene_1']}")
        print("=" * 50)

if __name__ == "__main__":
    process_facebook_data("posts.html")
