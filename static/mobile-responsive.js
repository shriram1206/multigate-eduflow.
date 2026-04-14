/**
 * MEF Portal - Mobile Responsive JavaScript
 * Handles mobile menu, touch interactions, and responsive behaviors
 */

(function() {
    'use strict';

    // ============================================
    // MOBILE MENU TOGGLE
    // ============================================
    
    function initMobileMenu() {
        // Create mobile menu toggle if it doesn't exist
        if (!document.querySelector('.mobile-menu-toggle')) {
            const toggle = document.createElement('button');
            toggle.className = 'mobile-menu-toggle';
            toggle.setAttribute('aria-label', 'Toggle navigation menu');
            toggle.innerHTML = '<span></span><span></span><span></span>';
            document.body.appendChild(toggle);
        }

        // Create mobile overlay if it doesn't exist
        if (!document.querySelector('.mobile-overlay')) {
            const overlay = document.createElement('div');
            overlay.className = 'mobile-overlay';
            document.body.appendChild(overlay);
        }

        const menuToggle = document.querySelector('.mobile-menu-toggle');
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.querySelector('.mobile-overlay');
        
        // For pages with navbar (like welcome.html) but no sidebar
        const navbar = document.querySelector('.navbar');
        const navLinks = navbar ? navbar.querySelector('.nav-links') : null;

        if (menuToggle) {
            // If there's a sidebar, use it
            if (sidebar) {
                menuToggle.addEventListener('click', function() {
                    this.classList.toggle('active');
                    sidebar.classList.toggle('active');
                    overlay.classList.toggle('active');
                    document.body.style.overflow = sidebar.classList.contains('active') ? 'hidden' : '';
                });

                // Close menu when overlay is clicked
                if (overlay) {
                    overlay.addEventListener('click', function() {
                        menuToggle.classList.remove('active');
                        sidebar.classList.remove('active');
                        overlay.classList.remove('active');
                        document.body.style.overflow = '';
                    });
                }

                // Close menu when navigation link is clicked
                const sidebarLinks = sidebar.querySelectorAll('.nav-link');
                sidebarLinks.forEach(link => {
                    link.addEventListener('click', function() {
                        if (window.innerWidth <= 767) {
                            menuToggle.classList.remove('active');
                            sidebar.classList.remove('active');
                            overlay.classList.remove('active');
                            document.body.style.overflow = '';
                        }
                    });
                });
            } 
            // For pages with navbar but no sidebar (like welcome page)
            else if (navbar && navLinks) {
                // Create a mobile menu container
                const mobileMenu = document.createElement('div');
                mobileMenu.className = 'mobile-menu-container';
                mobileMenu.style.cssText = `
                    position: fixed;
                    top: 0;
                    left: -100%;
                    width: 280px;
                    height: 100vh;
                    background: white;
                    box-shadow: 2px 0 10px rgba(0,0,0,0.1);
                    z-index: 1000;
                    transition: left 0.3s ease;
                    overflow-y: auto;
                    padding: 80px 20px 20px;
                `;
                
                // Clone navigation links
                const navLinksClone = navLinks.cloneNode(true);
                navLinksClone.style.cssText = `
                    display: flex !important;
                    flex-direction: column !important;
                    gap: 0 !important;
                `;
                
                // Style cloned links
                const links = navLinksClone.querySelectorAll('.nav-link');
                links.forEach(link => {
                    link.style.cssText = `
                        padding: 15px 20px !important;
                        border-bottom: 1px solid rgba(0,0,0,0.05) !important;
                        display: block !important;
                        width: 100% !important;
                        text-align: left !important;
                    `;
                });
                
                mobileMenu.appendChild(navLinksClone);
                document.body.appendChild(mobileMenu);
                
                // Toggle menu
                menuToggle.addEventListener('click', function() {
                    this.classList.toggle('active');
                    if (this.classList.contains('active')) {
                        mobileMenu.style.left = '0';
                        overlay.classList.add('active');
                        document.body.style.overflow = 'hidden';
                    } else {
                        mobileMenu.style.left = '-100%';
                        overlay.classList.remove('active');
                        document.body.style.overflow = '';
                    }
                });
                
                // Close on overlay click
                overlay.addEventListener('click', function() {
                    menuToggle.classList.remove('active');
                    mobileMenu.style.left = '-100%';
                    overlay.classList.remove('active');
                    document.body.style.overflow = '';
                });
                
                // Close on link click
                const mobileLinks = mobileMenu.querySelectorAll('.nav-link');
                mobileLinks.forEach(link => {
                    link.addEventListener('click', function() {
                        if (window.innerWidth <= 767) {
                            menuToggle.classList.remove('active');
                            mobileMenu.style.left = '-100%';
                            overlay.classList.remove('active');
                            document.body.style.overflow = '';
                        }
                    });
                });
            }
        }
    }

    // ============================================
    // RESPONSIVE TABLE WRAPPER
    // ============================================
    
    function makeTablesResponsive() {
        const tables = document.querySelectorAll('table:not(.responsive-wrapped)');
        tables.forEach(table => {
            if (!table.parentElement.classList.contains('table-responsive')) {
                const wrapper = document.createElement('div');
                wrapper.className = 'table-responsive';
                wrapper.style.overflowX = 'auto';
                wrapper.style.webkitOverflowScrolling = 'touch';
                table.parentNode.insertBefore(wrapper, table);
                wrapper.appendChild(table);
                table.classList.add('responsive-wrapped');
            }
        });
    }

    // ============================================
    // TOUCH-FRIENDLY FORM ENHANCEMENTS
    // ============================================
    
    function enhanceForms() {
        // Ensure input fields don't zoom on iOS
        const inputs = document.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            if (!input.style.fontSize) {
                input.style.fontSize = '16px';
            }
        });

        // Add clear button to text inputs on mobile
        if (window.innerWidth <= 767) {
            const textInputs = document.querySelectorAll('input[type="text"], input[type="email"], input[type="tel"]');
            textInputs.forEach(input => {
                if (!input.nextElementSibling || !input.nextElementSibling.classList.contains('clear-input')) {
                    input.addEventListener('input', function() {
                        if (this.value.length > 0) {
                            this.style.paddingRight = '40px';
                        } else {
                            this.style.paddingRight = '15px';
                        }
                    });
                }
            });
        }
    }

    // ============================================
    // VIEWPORT HEIGHT FIX (for mobile browsers)
    // ============================================
    
    function fixViewportHeight() {
        // Fix for mobile browsers that change viewport height on scroll
        const setVH = () => {
            const vh = window.innerHeight * 0.01;
            document.documentElement.style.setProperty('--vh', `${vh}px`);
        };
        
        setVH();
        window.addEventListener('resize', setVH);
        window.addEventListener('orientationchange', setVH);
    }

    // ============================================
    // TOUCH FEEDBACK
    // ============================================
    
    function addTouchFeedback() {
        const touchElements = document.querySelectorAll('.btn, button, .card, .nav-link, a.clickable');
        
        touchElements.forEach(element => {
            element.addEventListener('touchstart', function() {
                this.style.opacity = '0.7';
                this.style.transform = 'scale(0.98)';
            });
            
            element.addEventListener('touchend', function() {
                this.style.opacity = '';
                this.style.transform = '';
            });
            
            element.addEventListener('touchcancel', function() {
                this.style.opacity = '';
                this.style.transform = '';
            });
        });
    }

    // ============================================
    // RESPONSIVE IMAGES - LAZY LOADING
    // ============================================
    
    function initLazyLoading() {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        if (img.dataset.src) {
                            img.src = img.dataset.src;
                            img.classList.add('loaded');
                            observer.unobserve(img);
                        }
                    }
                });
            });

            const images = document.querySelectorAll('img[data-src]');
            images.forEach(img => imageObserver.observe(img));
        }
    }

    // ============================================
    // SMOOTH SCROLL FOR ANCHOR LINKS
    // ============================================
    
    function initSmoothScroll() {
        const anchorLinks = document.querySelectorAll('a[href^="#"]');
        anchorLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                const targetId = this.getAttribute('href');
                if (targetId === '#') return;
                
                const targetElement = document.querySelector(targetId);
                if (targetElement) {
                    e.preventDefault();
                    targetElement.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    }

    // ============================================
    // HANDLE ORIENTATION CHANGE
    // ============================================
    
    function handleOrientationChange() {
        window.addEventListener('orientationchange', function() {
            // Close mobile menu on orientation change
            const menuToggle = document.querySelector('.mobile-menu-toggle');
            const sidebar = document.querySelector('.sidebar');
            const overlay = document.querySelector('.mobile-overlay');
            
            if (menuToggle && sidebar) {
                menuToggle.classList.remove('active');
                sidebar.classList.remove('active');
                if (overlay) overlay.classList.remove('active');
                document.body.style.overflow = '';
            }
            
            // Trigger reflow
            setTimeout(() => {
                window.scrollTo(0, 0);
            }, 100);
        });
    }

    // ============================================
    // PREVENT DOUBLE TAP ZOOM ON BUTTONS
    // ============================================
    
    function preventDoubleTapZoom() {
        let lastTouchEnd = 0;
        document.addEventListener('touchend', function(event) {
            const now = Date.now();
            if (now - lastTouchEnd <= 300) {
                event.preventDefault();
            }
            lastTouchEnd = now;
        }, false);
    }

    // ============================================
    // BACK TO TOP BUTTON
    // ============================================
    
    function initBackToTop() {
        // Create back to top button if it doesn't exist
        if (!document.querySelector('.back-to-top')) {
            const backToTop = document.createElement('button');
            backToTop.className = 'back-to-top';
            backToTop.innerHTML = '<i class="fas fa-arrow-up"></i>';
            backToTop.setAttribute('aria-label', 'Back to top');
            backToTop.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                width: 56px;
                height: 56px;
                border-radius: 50%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                box-shadow: 0 4px 16px rgba(102, 126, 234, 0.4);
                cursor: pointer;
                display: none;
                z-index: 999;
                transition: all 0.3s ease;
                font-size: 20px;
                align-items: center;
                justify-content: center;
            `;
            document.body.appendChild(backToTop);

            // Show/hide based on scroll position
            window.addEventListener('scroll', function() {
                if (window.pageYOffset > 300) {
                    backToTop.style.display = 'flex';
                    backToTop.style.animation = 'fadeIn 0.3s ease';
                } else {
                    backToTop.style.display = 'none';
                }
            });

            // Hover effect
            backToTop.addEventListener('mouseenter', function() {
                this.style.transform = 'scale(1.1) translateY(-2px)';
                this.style.boxShadow = '0 6px 20px rgba(102, 126, 234, 0.5)';
            });

            backToTop.addEventListener('mouseleave', function() {
                this.style.transform = 'scale(1) translateY(0)';
                this.style.boxShadow = '0 4px 16px rgba(102, 126, 234, 0.4)';
            });

            // Scroll to top on click
            backToTop.addEventListener('click', function() {
                this.style.transform = 'scale(0.9)';
                setTimeout(() => {
                    this.style.transform = 'scale(1)';
                }, 100);
                
                window.scrollTo({
                    top: 0,
                    behavior: 'smooth'
                });
            });
        }
    }

    // ============================================
    // FORM VALIDATION IMPROVEMENTS
    // ============================================
    
    function enhanceFormValidation() {
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
            
            inputs.forEach(input => {
                // Show validation message on blur
                input.addEventListener('blur', function() {
                    if (!this.validity.valid) {
                        this.classList.add('invalid');
                        
                        // Add error message
                        if (!this.nextElementSibling || !this.nextElementSibling.classList.contains('error-message')) {
                            const errorMsg = document.createElement('span');
                            errorMsg.className = 'error-message';
                            errorMsg.style.cssText = 'color: #f06767; font-size: 14px; margin-top: 5px; display: block;';
                            errorMsg.textContent = this.validationMessage;
                            this.parentNode.insertBefore(errorMsg, this.nextSibling);
                        }
                    } else {
                        this.classList.remove('invalid');
                        const errorMsg = this.nextElementSibling;
                        if (errorMsg && errorMsg.classList.contains('error-message')) {
                            errorMsg.remove();
                        }
                    }
                });
                
                // Remove error on input
                input.addEventListener('input', function() {
                    if (this.validity.valid) {
                        this.classList.remove('invalid');
                        const errorMsg = this.nextElementSibling;
                        if (errorMsg && errorMsg.classList.contains('error-message')) {
                            errorMsg.remove();
                        }
                    }
                });
            });
        });
    }

    // ============================================
    // INITIALIZE ALL FUNCTIONS
    // ============================================
    
    function init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
            return;
        }

        // Initialize all mobile enhancements
        initMobileMenu();
        makeTablesResponsive();
        enhanceForms();
        fixViewportHeight();
        addTouchFeedback();
        initLazyLoading();
        initSmoothScroll();
        handleOrientationChange();
        preventDoubleTapZoom();
        initBackToTop();
        enhanceFormValidation();

        // Add fade-in animation to content
        document.body.classList.add('fade-in');

        console.log('✅ MEF Portal: Mobile enhancements loaded successfully');
    }

    // Start initialization
    init();

    // Expose some functions globally for debugging
    window.MEFPortal = {
        version: '1.0.0',
        refreshTables: makeTablesResponsive,
        refreshForms: enhanceForms
    };

})();
