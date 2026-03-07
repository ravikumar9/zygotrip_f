/**
 * Component Interactions - Goibibo-grade UI/UX
 * Production-ready JavaScript for dynamic components
 */

(function() {
  'use strict';
  
  // ============================================
  // DROPDOWN COMPONENT
  // ============================================
  function initDropdowns() {
    const dropdowns = document.querySelectorAll('.dropdown');
    
    dropdowns.forEach(dropdown => {
      const trigger = dropdown.querySelector('.dropdown-trigger, [data-dropdown-trigger]');
      const menu = dropdown.querySelector('.dropdown-menu');
      
      if (!trigger || !menu) return;
      
      trigger.addEventListener('click', function(e) {
        e.stopPropagation();
        
        // Close other dropdowns
        document.querySelectorAll('.dropdown.active').forEach(other => {
          if (other !== dropdown) {
            other.classList.remove('active');
          }
        });
        
        // Toggle current dropdown
        dropdown.classList.toggle('active');
      });
    });
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
      if (!e.target.closest('.dropdown')) {
        document.querySelectorAll('.dropdown.active').forEach(dropdown => {
          dropdown.classList.remove('active');
        });
      }
    });
  }
  
  // ============================================
  // MODAL COMPONENT
  // ============================================
  window.showModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    
    // Animate in
    requestAnimationFrame(() => {
      modal.style.opacity = '1';
    });
  };
  
  window.hideModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    // Animate out
    modal.style.opacity = '0';
    
    setTimeout(() => {
      modal.style.display = 'none';
      document.body.style.overflow = '';
    }, 200);
  };
  
  function initModals() {
    const modals = document.querySelectorAll('.modal-backdrop');
    
    modals.forEach(modal => {
      // Close on backdrop click
      modal.addEventListener('click', function(e) {
        if (e.target === modal) {
          hideModal(modal.id);
        }
      });
      
      // Close on close button
      const closeButtons = modal.querySelectorAll('[data-modal-close]');
      closeButtons.forEach(btn => {
        btn.addEventListener('click', () => hideModal(modal.id));
      });
      
      // Close on Escape key
      document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.style.display === 'flex') {
          hideModal(modal.id);
        }
      });
    });
  }
  
  // ============================================
  // STICKY SCROLL BEHAVIOR
  // ============================================
  function initStickyElements() {
    const stickyElements = document.querySelectorAll('.sticky-card, .sidebar');
    
    if (stickyElements.length === 0) return;
    
    let lastScrollTop = 0;
    
    window.addEventListener('scroll', function() {
      const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
      const scrollingDown = scrollTop > lastScrollTop;
      
      stickyElements.forEach(element => {
        const rect = element.getBoundingClientRect();
        const isStuck = rect.top <= parseInt(getComputedStyle(element).top || 0);
        
        if (isStuck) {
          element.classList.add('is-stuck');
        } else {
          element.classList.remove('is-stuck');
        }
      });
      
      lastScrollTop = scrollTop;
    }, { passive: true });
  }
  
  // ============================================
  // FILTER PANEL TOGGLE
  // ============================================
  function initFilterToggle() {
    const filterToggleBtn = document.querySelector('[data-filter-toggle]');
    const filterPanel = document.querySelector('.filters-sidebar, .sidebar');
    
    if (!filterToggleBtn || !filterPanel) return;
    
    filterToggleBtn.addEventListener('click', function() {
      filterPanel.classList.toggle('active');
      
      // On mobile, show as overlay
      if (window.innerWidth < 768) {
        filterPanel.style.position = 'fixed';
        filterPanel.style.top = '0';
        filterPanel.style.left = '0';
        filterPanel.style.right = '0';
        filterPanel.style.bottom = '0';
        filterPanel.style.zIndex = '999';
        filterPanel.style.background = 'white';
        filterPanel.style.overflowY = 'auto';
        
        // Add close button
        if (!filterPanel.querySelector('.filter-close')) {
          const closeBtn = document.createElement('button');
          closeBtn.className = 'filter-close btn btn-ghost';
          closeBtn.textContent = '×';
          closeBtn.style.position = 'absolute';
          closeBtn.style.top = '1rem';
          closeBtn.style.right = '1rem';
          closeBtn.style.fontSize = '2rem';
          closeBtn.onclick = function() {
            filterPanel.classList.remove('active');
            filterPanel.style.position = '';
          };
          filterPanel.prepend(closeBtn);
        }
      }
    });
  }
  
  // ============================================
  // FORM VALIDATION
  // ============================================
  function initFormValidation() {
    const forms = document.querySelectorAll('form[data-validate]');
    
    forms.forEach(form => {
      form.addEventListener('submit', function(e) {
        const requiredFields = form.querySelectorAll('[required]');
        let isValid = true;
        
        requiredFields.forEach(field => {
          if (!field.value.trim()) {
            isValid = false;
            field.classList.add('error');
            
            // Show error message
            let errorMsg = field.parentElement.querySelector('.form-error');
            if (!errorMsg) {
              errorMsg = document.createElement('span');
              errorMsg.className = 'form-error';
              errorMsg.textContent = 'This field is required';
              field.parentElement.appendChild(errorMsg);
            }
          } else {
            field.classList.remove('error');
            const errorMsg = field.parentElement.querySelector('.form-error');
            if (errorMsg) errorMsg.remove();
          }
        });
        
        if (!isValid) {
          e.preventDefault();
          
          // Scroll to first error
          const firstError = form.querySelector('.error');
          if (firstError) {
            firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
            firstError.focus();
          }
        }
      });
      
      // Remove error on input
      form.querySelectorAll('[required]').forEach(field => {
        field.addEventListener('input', function() {
          if (this.value.trim()) {
            this.classList.remove('error');
            const errorMsg = this.parentElement.querySelector('.form-error');
            if (errorMsg) errorMsg.remove();
          }
        });
      });
    });
  }
  
  // ============================================
  // LOADING STATES
  // ============================================
  window.showLoading = function(element) {
    if (typeof element === 'string') {
      element = document.querySelector(element);
    }
    if (!element) return;
    
    element.classList.add('loading');
    element.disabled = true;
    
    const originalText = element.textContent;
    element.dataset.originalText = originalText;
    element.textContent = 'Loading...';
  };
  
  window.hideLoading = function(element) {
    if (typeof element === 'string') {
      element = document.querySelector(element);
    }
    if (!element) return;
    
    element.classList.remove('loading');
    element.disabled = false;
    
    if (element.dataset.originalText) {
      element.textContent = element.dataset.originalText;
    }
  };
  
  // ============================================
  // TOAST NOTIFICATIONS
  // ============================================
  window.showToast = function(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `alert alert-${type}`;
    toast.textContent = message;
    toast.style.position = 'fixed';
    toast.style.top = '20px';
    toast.style.right = '20px';
    toast.style.zIndex = '9999';
    toast.style.minWidth = '250px';
    toast.style.animation = 'slideInRight 0.3s ease';
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.style.animation = 'slideOutRight 0.3s ease';
      setTimeout(() => {
        toast.remove();
      }, 300);
    }, duration);
  };
  
  // ============================================
  // SCROLL REVEAL ANIMATIONS
  // ============================================
  function initScrollReveal() {
    const revealElements = document.querySelectorAll('[data-reveal]');
    
    if (revealElements.length === 0) return;
    
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('revealed');
        }
      });
    }, {
      threshold: 0.1,
      rootMargin: '0px 0px -100px 0px'
    });
    
    revealElements.forEach(el => observer.observe(el));
  }
  
  // ============================================
  // DEBOUNCE UTILITY
  // ============================================
  window.debounce = function(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func.apply(this, args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  };
  
  // ============================================
  // THROTTLE UTILITY
  // ============================================
  window.throttle = function(func, limit) {
    let inThrottle;
    return function(...args) {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    };
  };
  
  // ============================================
  // SMOOTH SCROLL TO ANCHOR
  // ============================================
  function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function(e) {
        const href = this.getAttribute('href');
        if (href === '#') return;
        
        const target = document.querySelector(href);
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ 
            behavior: 'smooth',
            block: 'start'
          });
        }
      });
    });
  }
  
  // ============================================
  // MOBILE MENU TOGGLE
  // ============================================
  function initMobileMenu() {
    const mobileToggle = document.getElementById('mobileMenuToggle');
    const navLinks = document.querySelector('.navbar-nav');
    
    if (!mobileToggle || !navLinks) return;
    
    mobileToggle.addEventListener('click', function() {
      navLinks.classList.toggle('hidden-mobile');
      this.textContent = navLinks.classList.contains('hidden-mobile') ? '☰' : '×';
    });
  }
  
  // ============================================
  // NUMBER COUNTER ANIMATION
  // ============================================
  function animateCounter(element, target, duration = 1000) {
    const start = 0;
    const increment = target / (duration / 16); // 60fps
    let current = start;
    
    const timer = setInterval(() => {
      current += increment;
      if (current >= target) {
        element.textContent = target;
        clearInterval(timer);
      } else {
        element.textContent = Math.floor(current);
      }
    }, 16);
  }
  
  // ============================================
  // IMAGE LAZY LOADING
  // ============================================
  function initLazyLoading() {
    const images = document.querySelectorAll('img[loading="lazy"]');
    
    if ('loading' in HTMLImageElement.prototype) {
      // Browser supports native lazy loading
      return;
    }
    
    // Fallback for browsers that don't support lazy loading
    const imageObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          img.src = img.dataset.src;
          imageObserver.unobserve(img);
        }
      });
    });
    
    images.forEach(img => imageObserver.observe(img));
  }
  
  // ============================================
  // INITIALIZE ALL COMPONENTS
  // ============================================
  function init() {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
      return;
    }
    
    initDropdowns();
    initModals();
    initStickyElements();
    initFilterToggle();
    initFormValidation();
    initScrollReveal();
    initSmoothScroll();
    initMobileMenu();
    initLazyLoading();
    
    console.log('✓ Component interactions initialized');
  }
  
  // Auto-initialize
  init();
  
})();
