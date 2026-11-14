"""
Course services package initialization.

This package contains business logic services for course-related operations:
- course_service: Course creation, management, and operations
- enrollment_service: User enrollment and progress tracking
- quiz_service: Quiz creation and student assessment
- payment_service: Payment processing and transaction management
- analytics_service: Course analytics and reporting
"""

# Só módulos que existem: os antigos enrollment/quiz/payment/analytics_service nunca foram
# criados e o import falhava, deixando notas e certificados sempre partidos.
from .course_service import CourseService
from .grade_calculator import GradeCalculatorService

__all__ = [
    'CourseService',
    'GradeCalculatorService',
]
