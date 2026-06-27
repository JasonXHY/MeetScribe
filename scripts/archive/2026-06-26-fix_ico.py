"""
修复 ICO 图标文件 - 添加 Alpha 通道
"""

from PIL import Image
import os


def convert_png_to_rgba(png_path):
    """将 PNG 转换为 RGBA 模式"""
    img = Image.open(png_path)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
        img.save(png_path)
        print(f"Converted {png_path} to RGBA")
    else:
        print(f"{png_path} is already RGBA")
    return img


def generate_ico(source_img, ico_path, sizes=[16, 32, 48, 256]):
    """从 RGBA 图像生成 ICO 文件"""
    # 调整图像大小
    img = source_img.copy()
    
    # 保存为 ICO
    img.save(ico_path, format='ICO', sizes=[(s, s) for s in sizes])
    print(f"Generated {ico_path}")


def main():
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')
    
    # 处理 icon.png (1024x1024 源文件)
    icon_png = os.path.join(assets_dir, 'icon.png')
    if os.path.exists(icon_png):
        print(f"Processing {icon_png}...")
        img = convert_png_to_rgba(icon_png)
        
        # 生成 icon.ico
        ico_path = os.path.join(assets_dir, 'icon.ico')
        generate_ico(img, ico_path, sizes=[16, 32, 48, 256])
        
        # 生成各尺寸的 PNG
        for size in [16, 32, 48, 256]:
            resized = img.resize((size, size), Image.Resampling.LANCZOS)
            png_path = os.path.join(assets_dir, f'logo_{size}x{size}.png')
            resized.save(png_path)
            print(f"Generated {png_path}")
        
        # 生成 logo.ico (使用相同内容)
        logo_ico = os.path.join(assets_dir, 'logo.ico')
        generate_ico(img, logo_ico, sizes=[16, 32, 48, 256])
    
    # 验证结果
    print("\nVerification:")
    for f in ['logo_16x16.png', 'logo_32x32.png', 'logo_48x48.png', 'logo_256x256.png', 'icon.png', 'logo.ico', 'icon.ico']:
        path = os.path.join(assets_dir, f)
        if os.path.exists(path):
            img = Image.open(path)
            print(f"  {f}: mode={img.mode}, size={img.size}")
        else:
            print(f"  {f}: not found")


if __name__ == '__main__':
    main()
