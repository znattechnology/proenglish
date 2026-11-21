"""
Course models package initialization.

This package contains all course-related models organized by functionality:
- core: Main course, section, and chapter models
- enrollment: Enrollment and progress tracking models
- transactions: Payment and transaction models
- quizzes: Quiz and assessment models
- resources: Additional course resources
"""

# Import all models for backward compatibility
from .core import (
    Course,
    CourseSection, 
    Chapter,
    ChapterComment
)

from .enrollment import (
    CourseEnrollment,
    UserCourseProgress,
    ChapterProgress,
    VideoWatchLog,
)

from .transactions import (
    Transaction
)

from .quizzes import (
    ChapterQuiz,
    StudentQuizAttempt,
    TentativasExtraQuestionario,
)

from .resources import (
    ChapterResource
)

from .frases import FraseAula
from .exame import ExameOral
from .teste_basico import TesteNivelBasico

from .student_engagement import (
    CourseWishlist,
    CourseReview,
    StudentNote,
    StudentBookmark,
    CourseCertificate,
    SequenciaCertificado,
)

from .grading import (
    CourseGradingConfig,
    StudentCourseGrade,
    GradeHistory
)

# Make all models available at package level
__all__ = [
    'TesteNivelBasico',
    # Core models
    'Course',
    'CourseSection',
    'Chapter', 
    'ChapterComment',
    
    # Enrollment models
    'CourseEnrollment',
    'UserCourseProgress',
    'ChapterProgress',
    'VideoWatchLog',
    'TentativasExtraQuestionario',
    
    # Transaction models
    'Transaction',
    
    # Quiz models
    'ChapterQuiz',
    'StudentQuizAttempt',
    
    # Resource models
    'ChapterResource',
    'FraseAula',
    'ExameOral',

    # Student engagement models
    'CourseWishlist',
    'CourseReview',
    'StudentNote',
    'StudentBookmark',
    'CourseCertificate',
    'SequenciaCertificado',

    # Grading models
    'CourseGradingConfig',
    'StudentCourseGrade',
    'GradeHistory',
]