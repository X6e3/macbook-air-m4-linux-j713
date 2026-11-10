/*
 * x6e3 TL1 — AGX texture resource lifetime experiment
 * Based on the dxt-own.c supplied by the researcher, 2026-10-28.
 * New experiment; the original dxt-own.c and run.sh are not modified.
 *
 * Usage: tl1 A|B|C|D|E|O|V [size=1024]
 * A: upload -> delete -> finish
 * B: upload -> finish -> delete -> finish
 * C: upload -> draw -> delete -> finish
 * D: upload -> draw -> finish -> delete -> finish
 * E: upload -> draw -> unbind -> finish -> delete -> finish
 * O: upload -> finish -> draw -> finish -> readback -> delete -> finish
 *    (single-texture version of the original dxt-own.c control flow)
 * V: same as O, but uses deterministic white DXT5 blocks and verifies readback
 *
 * Separate process (fresh EGL context) per scenario. Run unprivileged.
 *   ASAHI_MESA_DEBUG=resource ./tl1 A 1024
 */
#define _POSIX_C_SOURCE 200809L
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <GLES2/gl2ext.h>
#include <inttypes.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifndef GL_COMPRESSED_RGBA_S3TC_DXT5_EXT
#define GL_COMPRESSED_RGBA_S3TC_DXT5_EXT 0x83F3
#endif

static void mark(const char *stage)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    fprintf(stderr, "TL1 ns=%" PRIu64 " stage=%s\n",
            (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec, stage);
    fflush(stderr);
}

static void fatal(const char *why)
{
    fprintf(stderr, "TL1 FATAL %s gl_error=0x%x\n", why, glGetError());
    fflush(stderr);
    exit(1);
}

static void glcheck(const char *where)
{
    GLenum e = glGetError();
    if (e != GL_NO_ERROR) {
        fprintf(stderr, "TL1 FATAL GL at %s: 0x%x\n", where, e);
        fflush(stderr);
        exit(1);
    }
}

static GLuint build_shader(GLenum type, const char *src)
{
    GLuint sh = glCreateShader(type);
    GLint good = 0;
    glShaderSource(sh, 1, &src, NULL);
    glCompileShader(sh);
    glGetShaderiv(sh, GL_COMPILE_STATUS, &good);
    if (!good) {
        char buf[2048];
        GLsizei n = 0;
        glGetShaderInfoLog(sh, (GLsizei)sizeof(buf), &n, buf);
        fprintf(stderr, "TL1 shader error: %.*s\n", (int)n, buf);
        fatal("shader compile");
    }
    return sh;
}

static GLuint make_program(void)
{
    const char *vs =
        "#version 300 es\n"
        "out vec2 uv;\n"
        "void main() {\n"
        " vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));\n"
        " uv = p; gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);\n"
        "}\n";
    const char *fs =
        "#version 300 es\n"
        "precision mediump float;\n"
        "uniform sampler2D t; in vec2 uv; out vec4 c;\n"
        "void main() { c = texture(t, uv); }\n";
    GLuint v = build_shader(GL_VERTEX_SHADER, vs);
    GLuint f = build_shader(GL_FRAGMENT_SHADER, fs);
    GLuint p = glCreateProgram();
    GLint linked = 0;
    glAttachShader(p, v);
    glAttachShader(p, f);
    glLinkProgram(p);
    glGetProgramiv(p, GL_LINK_STATUS, &linked);
    if (!linked) {
        char buf[2048];
        GLsizei n = 0;
        glGetProgramInfoLog(p, (GLsizei)sizeof(buf), &n, buf);
        fprintf(stderr, "TL1 link error: %.*s\n", (int)n, buf);
        fatal("program link");
    }
    glDeleteShader(v);
    glDeleteShader(f);
    glUseProgram(p);
    GLint loc = glGetUniformLocation(p, "t");
    if (loc < 0) fatal("sampler uniform missing");
    glUniform1i(loc, 0);
    glcheck("make_program");
    return p;
}

/* Same xorshift input as the original dxt-own.c; V uses valid opaque-white DXT5. */
static void fill_data(uint8_t *data, size_t n, int white)
{
    if (white) {
        const uint8_t block[16] = {
            255, 255, 0, 0, 0, 0, 0, 0, /* alpha endpoints / indices */
            255, 255, 255, 255, 0, 0, 0, 0 /* RGB565 white / indices */
        };
        for (size_t i = 0; i < n; i++) data[i] = block[i % sizeof(block)];
    } else {
        uint32_t x = UINT32_C(0x9e3779b9);
        for (size_t i = 0; i < n; i++) {
            x ^= x << 13; x ^= x >> 17; x ^= x << 5;
            data[i] = (uint8_t)x;
        }
    }
}

int main(int argc, char **argv)
{
    if (argc < 2 || argc > 3 || strlen(argv[1]) != 1 ||
        !strchr("ABCDEOV", argv[1][0])) {
        fprintf(stderr, "Usage: %s A|B|C|D|E|O|V [size=1024]\n", argv[0]);
        return 2;
    }
    char scenario = argv[1][0];
    int size = argc == 3 ? atoi(argv[2]) : 1024;
    if (size < 4 || size > 4096 || (size & (size - 1))) {
        fprintf(stderr, "Invalid power-of-two size\n");
        return 2;
    }

    printf("tl1_scenario=%c\nsize=%d\n", scenario, size);
    mark("egl_begin");
    EGLDisplay dpy = eglGetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA, NULL, NULL);
    if (dpy == EGL_NO_DISPLAY || !eglInitialize(dpy, NULL, NULL) ||
        !eglBindAPI(EGL_OPENGL_ES_API)) fatal("EGL setup");
    const EGLint ctx_attr[] = { EGL_CONTEXT_MAJOR_VERSION, 3, EGL_NONE };
    EGLContext ctx = eglCreateContext(dpy, EGL_NO_CONFIG_KHR, EGL_NO_CONTEXT, ctx_attr);
    if (ctx == EGL_NO_CONTEXT ||
        !eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, ctx))
        fatal("EGL context");
    printf("renderer=%s\nversion=%s\n",
           (const char *)glGetString(GL_RENDERER),
           (const char *)glGetString(GL_VERSION));
    const char *ext = (const char *)glGetString(GL_EXTENSIONS);
    printf("s3tc_extension=%s\n", ext && strstr(ext, "GL_EXT_texture_compression_s3tc") ? "yes" : "no");
    fflush(stdout);
    if (!ext || !strstr(ext, "GL_EXT_texture_compression_s3tc")) fatal("S3TC unavailable");
    mark("egl_end");

    GLuint rb = 0, fbo = 0;
    glGenRenderbuffers(1, &rb);
    glBindRenderbuffer(GL_RENDERBUFFER, rb);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, 64, 64);
    glGenFramebuffers(1, &fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, rb);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
        fatal("FBO incomplete");
    glViewport(0, 0, 64, 64);
    GLuint prog = make_program();
    GLuint vao = 0;
    glGenVertexArrays(1, &vao);
    glBindVertexArray(vao);
    glActiveTexture(GL_TEXTURE0);
    glFinish(); /* setup-only fence, identical for all scenarios */
    glcheck("setup");
    mark("setup_end");

    int levels = 0;
    for (int s = size; s >= 1; s >>= 1) levels++;
    size_t top = (size_t)((size + 3) / 4) * ((size + 3) / 4) * 16;
    uint8_t *data = malloc(top);
    if (!data) fatal("allocation");
    fill_data(data, top, scenario == 'V');
    printf("levels=%d\ndxt5_bytes_per_texture=", levels);
    size_t total_dxt = 0;
    for (int l = 0; l < levels; l++) {
        int s = size >> l ? size >> l : 1;
        total_dxt += (size_t)((s + 3) / 4) * ((s + 3) / 4) * 16;
    }
    printf("%zu\n", total_dxt);
    fflush(stdout);

    GLuint tex = 0;
    glGenTextures(1, &tex);
    mark("upload_begin");
    glBindTexture(GL_TEXTURE_2D, tex);
    /* Deliberately retain the original default GL_NEAREST_MIPMAP_LINEAR. */
    for (int l = 0; l < levels; l++) {
        int s = size >> l ? size >> l : 1;
        GLsizei bytes = ((s + 3) / 4) * ((s + 3) / 4) * 16;
        char label[64];
        snprintf(label, sizeof(label), "upload_level_%02d_begin", l);
        mark(label);
        glCompressedTexImage2D(GL_TEXTURE_2D, l,
                               GL_COMPRESSED_RGBA_S3TC_DXT5_EXT,
                               s, s, 0, bytes, data);
        glcheck("glCompressedTexImage2D");
        snprintf(label, sizeof(label), "upload_level_%02d_end", l);
        mark(label);
    }
    mark("upload_end");

    if (scenario == 'B' || scenario == 'O' || scenario == 'V') {
        mark("post_upload_finish_begin");
        glFinish();
        mark("post_upload_finish_end");
    }
    if (scenario == 'C' || scenario == 'D' || scenario == 'E' || scenario == 'O' || scenario == 'V') {
        mark("draw_begin");
        glDrawArrays(GL_TRIANGLES, 0, 3);
        glcheck("draw");
        mark("draw_end");
    }
    if (scenario == 'E') {
        mark("unbind_begin");
        glBindTexture(GL_TEXTURE_2D, 0);
        mark("unbind_end");
    }
    if (scenario == 'D' || scenario == 'E' || scenario == 'O' || scenario == 'V') {
        mark("post_draw_finish_begin");
        glFinish();
        mark("post_draw_finish_end");
    }
    if (scenario == 'O' || scenario == 'V') {
        mark("readback_begin");
        uint8_t px[4] = {0, 0, 0, 0};
        glPixelStorei(GL_PACK_ALIGNMENT, 1);
        glReadPixels(32, 32, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, px);
        glcheck("readback");
        printf("pixel_rgba=%u,%u,%u,%u\n", px[0], px[1], px[2], px[3]);
        if (scenario == 'V' &&
            (px[0] != 255 || px[1] != 255 || px[2] != 255 || px[3] != 255))
            fatal("white DXT5 pixel mismatch");
        mark("readback_end");
    }

    mark("delete_begin");
    glDeleteTextures(1, &tex);
    glcheck("delete");
    mark("delete_end");
    mark("post_delete_finish_begin");
    glFinish();
    mark("post_delete_finish_end");

    mark("other_objects_delete_begin");
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    glDeleteFramebuffers(1, &fbo);
    glDeleteRenderbuffers(1, &rb);
    glDeleteVertexArrays(1, &vao);
    glDeleteProgram(prog);
    glFinish();
    mark("other_objects_delete_end");
    mark("context_unbind_begin");
    if (!eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT))
        fatal("context unbind");
    mark("context_unbind_end");
    mark("context_destroy_begin");
    if (!eglDestroyContext(dpy, ctx)) {
        fprintf(stderr, "TL1 FATAL eglDestroyContext\n");
        return 1;
    }
    mark("context_destroy_end");
    mark("egl_terminate_begin");
    eglTerminate(dpy);
    mark("egl_terminate_end");
    free(data);
    printf("done=1\n");
    fflush(stdout);
    return 0;
}
