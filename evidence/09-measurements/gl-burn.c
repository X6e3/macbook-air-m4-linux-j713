/*
 * gl-burn: full GPU load on Linux for the J713 thermal test, the GL counterpart of the macOS gpu-load (an
 * FMA-bound Metal kernel). One full-screen triangle into a 2560x1600 offscreen framebuffer with an FMA-bound
 * fragment shader, drawn back to back. No window and no compositor: EGL surfaceless.
 *
 * It refuses to run unless the renderer is the M4 GPU, so a leftover software-rendering variable cannot turn
 * it into a CPU test.
 *
 *   gcc -O2 -Wall -o gl-burn gl-burn.c -lEGL -lGLESv2
 *   gl-burn <seconds>        prints the renderer, then draws per second every 10 s
 */
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES3/gl3.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define W 2560
#define H 1600
#define ITER 1024

static const char *vs_src =
    "#version 300 es\n"
    "void main() {\n"
    "    vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));\n"
    "    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);\n"
    "}\n";
static const char *fs_src =
    "#version 300 es\n"
    "precision highp float;\n"
    "uniform int n;\n"
    "out vec4 c;\n"
    "void main() {\n"
    "    float a = gl_FragCoord.x * 1e-6, b = 1.0001, d = 0.9999, e = 0.5;\n"
    "    for (int i = 0; i < n; i++) { a = a * b + d; b = b * d + e; d = d * e + a; e = e * a + b; }\n"
    "    c = vec4(a, b, d, e);\n"
    "}\n";

static volatile sig_atomic_t stop;

static void on_signal(int sig)
{
    (void)sig;
    stop = 1;
}

static double now(void)
{
    struct timespec t;

    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}

static GLuint shader(GLenum type, const char *src)
{
    GLuint s = glCreateShader(type);
    GLint ok;
    char log[1024];

    glShaderSource(s, 1, &src, NULL);
    glCompileShader(s);
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        glGetShaderInfoLog(s, sizeof(log), NULL, log);
        fprintf(stderr, "shader: %s\n", log);
        exit(1);
    }
    return s;
}

int main(int argc, char **argv)
{
    static const EGLint ctx_attr[] = {EGL_CONTEXT_MAJOR_VERSION, 3, EGL_NONE};
    double secs = argc > 1 ? atof(argv[1]) : 60;
    EGLDisplay dpy = eglGetPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA, NULL, NULL);
    EGLContext ctx;
    GLuint rb, fb, vao, prog;
    GLint linked;
    const char *renderer;

    if (dpy == EGL_NO_DISPLAY || !eglInitialize(dpy, NULL, NULL) || !eglBindAPI(EGL_OPENGL_ES_API)) {
        fprintf(stderr, "EGL surfaceless display failed (0x%x)\n", eglGetError());
        return 1;
    }
    ctx = eglCreateContext(dpy, EGL_NO_CONFIG_KHR, EGL_NO_CONTEXT, ctx_attr);
    if (ctx == EGL_NO_CONTEXT || !eglMakeCurrent(dpy, EGL_NO_SURFACE, EGL_NO_SURFACE, ctx)) {
        fprintf(stderr, "GLES 3 context failed (0x%x)\n", eglGetError());
        return 1;
    }
    renderer = (const char *)glGetString(GL_RENDERER);
    printf("renderer: %s\nversion: %s\n", renderer ? renderer : "?", (const char *)glGetString(GL_VERSION));
    if (!renderer || !strstr(renderer, "Apple")) {
        fprintf(stderr, "STOP: the renderer is not the M4 GPU\n");
        return 3;
    }

    glGenRenderbuffers(1, &rb);
    glBindRenderbuffer(GL_RENDERBUFFER, rb);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, W, H);
    glGenFramebuffers(1, &fb);
    glBindFramebuffer(GL_FRAMEBUFFER, fb);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_RENDERBUFFER, rb);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
        fprintf(stderr, "framebuffer incomplete\n");
        return 1;
    }
    glViewport(0, 0, W, H);

    prog = glCreateProgram();
    glAttachShader(prog, shader(GL_VERTEX_SHADER, vs_src));
    glAttachShader(prog, shader(GL_FRAGMENT_SHADER, fs_src));
    glLinkProgram(prog);
    glGetProgramiv(prog, GL_LINK_STATUS, &linked);
    if (!linked) {
        fprintf(stderr, "link failed\n");
        return 1;
    }
    glUseProgram(prog);
    glUniform1i(glGetUniformLocation(prog, "n"), ITER);
    glGenVertexArrays(1, &vao);
    glBindVertexArray(vao);

    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);
    printf("load: %dx%d, %d FMA x4 per pixel, for %.0f s\n", W, H, ITER, secs);
    fflush(stdout);

    double t0 = now(), mark = t0;
    long draws = 0, at_mark = 0;

    while (!stop && now() - t0 < secs) {
        for (int i = 0; i < 4; i++)
            glDrawArrays(GL_TRIANGLES, 0, 3);
        glFinish();
        draws += 4;
        if (now() - mark >= 10) {
            double t = now();

            printf("%.0f s: %.2f draws/s\n", t - t0, (draws - at_mark) / (t - mark));
            fflush(stdout);
            mark = t;
            at_mark = draws;
        }
    }
    printf("done: %ld draws in %.1f s, GL error 0x%x%s\n", draws, now() - t0, glGetError(), stop ? " (stopped)" : "");
    return 0;
}
