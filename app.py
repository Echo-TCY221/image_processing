import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from werkzeug.utils import secure_filename
from PIL import Image
import zipfile
from io import BytesIO
from flask import send_file, jsonify
from flask_wtf import CSRFProtect


app = Flask(__name__)
UPLOAD_FOLDER_HEAD = 'static/head_images'
UPLOAD_FOLDER_MAIN = 'static/main_images'
COMBINED_FOLDER = 'static/combined_images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['SECRET_KEY'] = 'supersecretkey'  # 设置SECRET_KEY
csrf = CSRFProtect(app)
app.config['UPLOAD_FOLDER_HEAD'] = UPLOAD_FOLDER_HEAD
app.config['UPLOAD_FOLDER_MAIN'] = UPLOAD_FOLDER_MAIN
app.config['COMBINED_FOLDER'] = COMBINED_FOLDER

if not os.path.exists(UPLOAD_FOLDER_HEAD):
    os.makedirs(UPLOAD_FOLDER_HEAD)

if not os.path.exists(UPLOAD_FOLDER_MAIN):
    os.makedirs(UPLOAD_FOLDER_MAIN)

if not os.path.exists(COMBINED_FOLDER):
    os.makedirs(COMBINED_FOLDER)


def resize_image(input_image_path, output_image_path, target_size=(4039, 4039)):
    """图片缩放"""
    try:
        image = Image.open(input_image_path)

        if image.mode == 'RGBA':
            image = image.convert('RGB')

        if image.mode != 'RGB':
            image = image.convert('RGB')

        resized_image = image.resize(target_size, Image.LANCZOS)
        resized_image.save(output_image_path)
    except Exception as e:
        print(f"错误: {e}")


def combine_images_with_transparency(base_image_path, overlay_image_path, output_image_path):
    """合成图片并处理透明度"""
    try:
        image1 = Image.open(overlay_image_path).convert("RGBA")
        image2 = Image.open(base_image_path).convert("RGB").convert("RGBA")

        image1_width, image1_height = image1.size
        image2_width, image2_height = image2.size

        position = ((image1_width - image2_width) // 2, (image1_height - image2_height) // 2)
        canvas = Image.new("RGBA", image1.size)
        canvas.paste(image2, position, image2)
        canvas.paste(image1, (0, 0), image1)

        canvas.save(output_image_path, format="PNG")
    except Exception as e:
        print(f"错误: {e}")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    head_images = os.listdir(UPLOAD_FOLDER_HEAD)
    main_images = os.listdir(UPLOAD_FOLDER_MAIN)
    return render_template('index.html', head_images=head_images, main_images=main_images)


@app.route('/upload_head', methods=['POST'])
@csrf.exempt
def upload_head():
    if 'file' not in request.files:
        flash('无文件部分...', 'error')
        return redirect(request.url)
    files = request.files.getlist('file')
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER_HEAD'], filename))
    flash('头部图像上传成功!', 'success')
    return redirect(url_for('index'))


@app.route('/upload_main', methods=['POST'])
@csrf.exempt
def upload_main():
    if 'file' not in request.files:
        flash('无文件部分...', 'error')
        return redirect(request.url)
    files = request.files.getlist('file')
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER_MAIN'], filename))
    flash('主图片上传成功!', 'success')
    return redirect(url_for('index'))


@app.route('/combine', methods=['POST'])
@csrf.exempt
def combine():
    head_image = request.form.get('head_image')
    main_image = request.form.get('main_image')
    if head_image and main_image:
        head_path = os.path.join(UPLOAD_FOLDER_HEAD, head_image)
        main_path = os.path.join(UPLOAD_FOLDER_MAIN, main_image)
        combined_image_name = os.path.splitext(main_image)[0] + '.png'
        combined_image_path = os.path.join(COMBINED_FOLDER, combined_image_name)

        try:
            resize_image(main_path, main_path, target_size=(4039, 4039))
            combine_images_with_transparency(main_path, head_path, combined_image_path)
            resize_image(combined_image_path, combined_image_path, target_size=(800, 800))
            return jsonify({'status': 'success', 'message': '图片合成完成!'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'图片合成失败: {e}'})
    else:
        return jsonify({'status': 'error', 'message': '请选择要合并的图像...'})


@app.route('/delete_image/<folder>/<filename>')
def delete_image(folder, filename):
    if folder == 'head':
        path = os.path.join(UPLOAD_FOLDER_HEAD, filename)
    elif folder == 'main':
        path = os.path.join(UPLOAD_FOLDER_MAIN, filename)
    else:
        return redirect(url_for('index'))
    if os.path.exists(path):
        os.remove(path)
        flash(f'{filename} 成功删除!', 'success')
    return redirect(url_for('index'))


@app.route('/download')
def download():
    combined_images = os.listdir(COMBINED_FOLDER)
    return render_template('download.html', combined_images=combined_images)


@app.route('/download_files', methods=['POST'])
@csrf.exempt
def download_files():
    selected_images = request.form.getlist('selected_images')
    if selected_images:
        if len(selected_images) == 1:
            image_path = os.path.join(app.config['COMBINED_FOLDER'], selected_images[0])
            return send_file(
                image_path,
                as_attachment=True,
                download_name=selected_images[0]
            )
        else:
            memory_file = BytesIO()
            with zipfile.ZipFile(memory_file, 'w') as zf:
                for image in selected_images:
                    file_path = os.path.join(app.config['COMBINED_FOLDER'], image)
                    zf.write(file_path, os.path.basename(file_path))

            memory_file.seek(0)

            return send_file(
                memory_file,
                mimetype='application/zip',
                as_attachment=True,
                download_name='combined_images.zip'
            )
    else:
        flash('请选择要下载的图像...')
        return redirect(url_for('download'))


@app.route('/delete_selected_images', methods=['POST'])
def delete_selected_images():
    data = request.get_json()
    selected_images = data.get('images', [])

    if selected_images:
        try:
            for image in selected_images:
                file_path = os.path.join(app.config['COMBINED_FOLDER'], image)
                if os.path.exists(file_path):
                    os.remove(file_path)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    return jsonify({'success': False, 'error': '没有选择图像...'})


@app.route('/return_home')
def return_home():
    return redirect(url_for('index'))


if __name__ == '__main__':
    host = '127.0.0.1'
    app.run(debug=True, host=host)
