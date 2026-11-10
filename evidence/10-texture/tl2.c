/*
 * x6e3 TL2 — Selective Sampling / AGX Gallium texture-resource lifetime
 * Based on the researcher's dxt-own.c and the TL1 reproducer (2026-10-28).
 * Run unprivileged with ASAHI_MESA_DEBUG=resource.
 *
 * A: 32 textures, draw 0
 * B: 32 textures, draw 1
 * C: 32 textures, draw 16
 * D: 32 textures, draw 32
 * E: 32 textures, draw 0, set GL_TEXTURE_MAX_LEVEL before upload
 *
 * Markers bracket real GL calls. Each scenario runs in a separate EGL process.
 * No changes to the system Mesa, kernel, Xonotic, or existing experiments.
 */
#define _POSIX_C_SOURCE 200809L
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <GLES2/gl2ext.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifndef GL_COMPRESSED_RGBA_S3TC_DXT5_EXT
#define GL_COMPRESSED_RGBA_S3TC_DXT5_EXT 0x83F3
#endif
#define NUM_TEX 32
#define TEX_SIZE 1024

static void stage(const char *name)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    fprintf(stderr, "TL2 ns=%" PRIu64 " stage=%s\n",
        (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec, name);
    fflush(stderr);
}
static void stage_index(const char *verb, int i, const char *suffix)
{
    char name[96];
    snprintf(name, sizeof(name), "%s_%02d_%s", verb, i, suffix);
    stage(name);
}
static void die(const char *msg)
{
    fprintf(stderr, "TL2 FATAL %s gl_error=0x%x\n", msg, glGetError());
    fflush(stderr);
    exit(1);
}
static void check(const char *msg)
{
    GLenum e = glGetError();
    if (e != GL_NO_ERROR) {
        fprintf(stderr, "TL2 FATAL %s gl_error=0x%x\n", msg, e);
        exit(1);
    }
}
static GLuint shader(GLenum type, const char *src)
{
    GLuint s = glCreateShader(type);
    GLint ok = 0;
    glShaderSource(s, 1, &src, NULL);
    glCompileShader(s);
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char info[2048]; GLsizei n = 0;
        glGetShaderInfoLog(s, (GLsizei)sizeof(info), &n, info);
        fprintf(stderr, "TL2 shader: %.*s\n", (int)n, info);
        die("compile");
    }
    return s;
}
static GLuint program(void)
{
    const char *vs =
        "#version 300 es\n"
        "out vec2 uv;\n"
        "void main() {\n"
        " vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));\n"
        " uv=p; gl_Position=vec4(p*2.0-1.0,0.0,1.0);\n"
        "}\n";
    const char *fs =
        "#version 300 es\n"
        "precision mediump float;\n"
        "uniform sampler2D t; in vec2 uv; out vec4 c;\n"
        "void main() { c = texture(t, uv); }\n";
    GLuint v = shader(GL_VERTEX_SHADER, vs);
    GLuint f = shader(GL_FRAGMENT_SHADER, fs);
    GLuint p = glCreateProgram(); GLint ok = 0;
    glAttachShader(p, v); glAttachShader(p, f);
    glLinkProgram(p); glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) die("link");
    glDeleteShader(v); glDeleteShader(f);
    glUseProgram(p);
    GLint sampler = glGetUniformLocation(p, "t");
    if (sampler < 0) die("sampler uniform");
    glUniform1i(sampler, 0);
    check("program");
    return p;
}
int main(int argc, char **argv)
{
    if (argc != 2 || strlen(argv[1]) != 1 || !strchr("ABCDE", argv[1][0])) {
        fprintf(stderr, "Usage: %s A|B|C|D|E\n", argv[0]);
        return 2;
    }
    const char sc = argv[1][0];
    const int draw_count = sc == 'B' ? 1 : sc == 'C' ? 16 : sc == 'D' ? 32 : 0;
    const int maxlevel = sc == 'E';
    printf("scenario=%c\ntextures=%d\ndraw_count=%d\nmaxlevel=%d\n",
           sc, NUM_TEX, draw_count, maxlevel);
    stage("egl_begin");
    EGLDisplay d = eglGetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA, NULL, NULL);
    if (d == EGL_NO_DISPLAY || !eglInitialize(d, NULL, NULL) ||
        !eglBindAPI(EGL_OPENGL_ES_API)) die("EGL init");
    const EGLint attrs[] = { EGL_CONTEXT_MAJOR_VERSION, 3, EGL_NONE };
    EGLContext ctx = eglCreateContext(d, EGL_NO_CONFIG_KHR, EGL_NO_CONTEXT, attrs);
    if (ctx == EGL_NO_CONTEXT ||
        !eglMakeCurrent(d, EGL_NO_SURFACE, EGL_NO_SURFACE, ctx)) die("EGL context");
    printf("renderer=%s\nversion=%s\n", glGetString(GL_RENDERER), glGetString(GL_VERSION));
    const char *ext = (const char *)glGetString(GL_EXTENSIONS);
    printf("s3tc_extension=%s\n", ext && strstr(ext, "GL_EXT_texture_compression_s3tc") ? "yes" : "no");
    fflush(stdout);
    if (!ext || !strstr(ext, "GL_EXT_texture_compression_s3tc")) die("S3TC unavailable");
    stage("egl_end");

    GLuint rb=0, fbo=0, vao=0;
    glGenRenderbuffers(1, &rb); glBindRenderbuffer(GL_RENDERBUFFER, rb);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, 64, 64);
    glGenFramebuffers(1, &fbo); glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, rb);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
        die("framebuffer incomplete");
    glViewport(0,0,64,64);
    GLuint p = program();
    glGenVertexArrays(1,&vao); glBindVertexArray(vao);
    glActiveTexture(GL_TEXTURE0);
    glClearColor(0.f,0.f,0.f,1.f);
    glClear(GL_COLOR_BUFFER_BIT);
    glFinish();
    check("setup");
    stage("setup_end");

    /* Valid opaque-white DXT5, including all mip levels: content-independent sampling control. */
    const uint8_t white[16] = {255,255,0,0,0,0,0,0,255,255,255,255,0,0,0,0};
    const size_t top=(size_t)(TEX_SIZE / 4)*(TEX_SIZE / 4)*16;
    uint8_t *bytes=malloc(top);
    if (!bytes) die("malloc");
    for (size_t j=0;j<top;j++) bytes[j]=white[j%16];
    GLuint tex[NUM_TEX] = {0};
    glGenTextures(NUM_TEX,tex);
    check("glGenTextures");
    stage("upload_begin");
    for (int i=0;i<NUM_TEX;i++) {
        stage_index("texture",i,"begin");
        glBindTexture(GL_TEXTURE_2D, tex[i]);
        if (maxlevel) glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, 10);
        for (int l=0;l<=10;l++) {
            int sz=TEX_SIZE>>l;
            if (sz<1) sz=1;
            GLsizei len=((sz+3)/4)*((sz+3)/4)*16;
            glCompressedTexImage2D(GL_TEXTURE_2D,l,GL_COMPRESSED_RGBA_S3TC_DXT5_EXT,
                                   sz,sz,0,len,bytes);
            check("compressed level upload");
        }
        stage_index("texture",i,"end");
    }
    stage("upload_end");
    stage("draw_batch_begin");
    for (int i=0;i<draw_count;i++) {
        stage_index("draw",i,"begin");
        glBindTexture(GL_TEXTURE_2D,tex[i]);
        glDrawArrays(GL_TRIANGLES,0,3);
        check("draw texture");
        stage_index("draw",i,"end");
    }
    stage("draw_batch_end");
    stage("finish_before_checkpoint_begin");
    glFinish();
    stage("finish_before_checkpoint_end");
    /* This exact marker is the principal comparison point: no GL texture deleted yet. */
    stage("checkpoint_before_delete");

    /* Readback happens AFTER the allocation snapshot, so it cannot change that result. */
    stage("readback_begin");
    uint8_t px[4]={0,0,0,0};
    glPixelStorei(GL_PACK_ALIGNMENT,1);
    glReadPixels(32,32,1,1,GL_RGBA,GL_UNSIGNED_BYTE,px);
    check("readback");
    printf("pixel_rgba=%u,%u,%u,%u\n",px[0],px[1],px[2],px[3]);
    const uint8_t expected=draw_count ? 255 : 0;
    if (px[0]!=expected || px[1]!=expected || px[2]!=expected || px[3]!=255)
        die("readback pixel mismatch");
    stage("readback_end");
    stage("delete_begin");
    glDeleteTextures(NUM_TEX,tex);
    check("delete");
    stage("delete_end");
    stage("finish_after_delete_begin");
    glFinish();
    stage("finish_after_delete_end");
    glBindFramebuffer(GL_FRAMEBUFFER,0);
    glDeleteFramebuffers(1,&fbo); glDeleteRenderbuffers(1,&rb);
    glDeleteVertexArrays(1,&vao); glDeleteProgram(p);
    glFinish(); check("cleanup");
    stage("context_destroy_begin");
    if (!eglMakeCurrent(d,EGL_NO_SURFACE,EGL_NO_SURFACE,EGL_NO_CONTEXT) ||
        !eglDestroyContext(d,ctx)) die("context destroy");
    stage("context_destroy_end");
    eglTerminate(d);
    free(bytes);
    printf("done=1\n"); fflush(stdout);
    return 0;
}
