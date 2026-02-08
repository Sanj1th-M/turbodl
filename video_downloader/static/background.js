class Particle {
    constructor(x, y, canvasWidth, canvasHeight) {
        this.x = x;
        this.y = y;
        this.baseX = x;
        this.baseY = y;

        // Digital Variant Logic
        this.size = Math.random() * 30 + 5; // Varying size: larger blocks
        this.color = '#ffffff';
        this.baseAlpha = Math.random() * 0.15 + 0.02; // Very subtle to distinct
        this.alpha = this.baseAlpha;
        this.velX = (Math.random() - 0.5) * 0.2; // Slow drift
        this.velY = (Math.random() - 0.5) * 0.2;
        this.isOutline = Math.random() > 0.5; // 50% chance of being an outline
    }

    draw(ctx) {
        ctx.globalAlpha = this.alpha;

        if (this.isOutline) {
            ctx.strokeStyle = this.color;
            ctx.lineWidth = 1.5;
            ctx.strokeRect(this.x, this.y, this.size, this.size);
        } else {
            ctx.fillStyle = this.color;
            ctx.fillRect(this.x, this.y, this.size, this.size);
        }

        // Reset global alpha
        ctx.globalAlpha = 1;
    }

    update(canvasWidth, canvasHeight) {
        // Drift logic
        this.x += this.velX;
        this.y += this.velY;

        // Wrap around
        if (this.x < -this.size) this.x = canvasWidth;
        if (this.x > canvasWidth) this.x = -this.size;
        if (this.y < -this.size) this.y = canvasHeight;
        if (this.y > canvasHeight) this.y = -this.size;
    }
}

const initBackground = () => {
    const canvas = document.getElementById('bgCanvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let animationFrameId;
    let particlesArray = [];

    const init = () => {
        particlesArray = [];
        // Digital particle count formula from React component: (w * h) / 6700
        const particleCount = (canvas.width * canvas.height) / 6700;

        for (let i = 0; i < particleCount; i++) {
            const x = Math.random() * canvas.width;
            const y = Math.random() * canvas.height;
            particlesArray.push(new Particle(x, y, canvas.width, canvas.height));
        }
    };

    const animate = () => {
        // Clear canvas completely for digital variant
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        for (let i = 0; i < particlesArray.length; i++) {
            particlesArray[i].update(canvas.width, canvas.height);
            particlesArray[i].draw(ctx);
        }
        animationFrameId = requestAnimationFrame(animate);
    };

    const handleResize = () => {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        init();
    };

    // Initialize
    handleResize();
    animate();

    // Event Listeners
    window.addEventListener('resize', handleResize);
};

// Start when DOM is ready
document.addEventListener('DOMContentLoaded', initBackground);
