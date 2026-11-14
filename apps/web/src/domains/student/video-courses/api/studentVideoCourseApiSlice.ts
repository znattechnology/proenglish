import { createApi } from '@reduxjs/toolkit/query/react';
import { studentVideoCoursesBaseQuery } from '../../../shared/api/baseQuery';
import type {
  StudentVideoCourse,
  StudentVideoSection,
  StudentVideoChapter,
  CourseEnrollment,
  StudentCourseProgress,
  VideoProgressUpdate,
  ChapterCompletion,
  CourseEnrollmentRequest,
  CourseSearchParams,
  CourseReview,
  CreateReviewData,
  StudentVideoAnalytics,
  CourseCertificate,
  CourseRecommendation,
  StudentNote,
  StudentBookmark,
} from '../types';

// Chapter Resource interface from legacy structure
export interface ChapterResource {
  id?: string;
  title: string;
  description?: string;
  resource_type: "PDF" | "LINK" | "VIDEO" | "CODE" | "WORKSHEET" | "AUDIO" | "IMAGE";
  file?: string;
  external_url?: string;
  file_size?: number;
  download_count?: number;
  order?: number;
  is_featured?: boolean;
  created_by?: string;
  created_by_name?: string;
  file_url?: string;
  created_at?: string;
  updated_at?: string;
}

// Chapter Quiz interface from legacy structure
export interface ChapterQuiz {
  id?: string;
  chapter?: string;
  chapter_title?: string;
  practice_lesson: string;
  practice_lesson_title?: string;
  title: string;
  description?: string;
  points_reward?: number;
  hearts_cost?: number;
  passing_score?: number;
  time_limit?: number;
  max_attempts?: number;
  total_attempts?: number;
  total_completions?: number;
  average_score?: number;
  completion_rate?: number;
  is_active?: boolean;
  created_by?: string;
  created_by_name?: string;
  created_at?: string;
  updated_at?: string;
}

// Student Video Course API slice
export const studentVideoCourseApiSlice = createApi({
  reducerPath: 'studentVideoCourseApi',
  baseQuery: studentVideoCoursesBaseQuery,
  tagTypes: [
    'StudentVideoCourse',
    'CourseEnrollment',
    'VideoProgress',
    'CourseReview',
    'StudentVideoAnalytics',
    'CourseCertificate',
    'CourseRecommendation',
    'StudentNote',
    'StudentBookmark',
    'ChapterResource',
    'ChapterQuiz',
  ],
  endpoints: (builder) => ({
    
    // ===== COURSE DISCOVERY =====
    
    getAvailableVideoCourses: builder.query<{ data: StudentVideoCourse[]; total: number }, CourseSearchParams>({
      query: (params = {}) => ({
        url: '/',
        params: {
          ...params,
          status: 'Published', // Only published courses for students
        },
      }),
      providesTags: ['StudentVideoCourse'],
    }),

    getVideoCourseById: builder.query<StudentVideoCourse, string>({
      query: (courseId) => ({
        url: `/${courseId}/`,
        params: {
          include_chapter_data: true, // Request full chapter data including quiz_data, practice_selection
        },
      }),
      transformResponse: (response: { message?: string; data?: StudentVideoCourse } | StudentVideoCourse) => {
        // Se a resposta tem o formato {message, data}, extrair apenas data
        if (response && 'data' in response && response.data) {
          return response.data;
        }
        // Caso contrário, retornar como está
        return response as StudentVideoCourse;
      },
      providesTags: (result, error, courseId) => [
        { type: 'StudentVideoCourse', id: courseId },
      ],
    }),
    // ===== COURSE ENROLLMENT =====
    
    enrollInVideoCourse: builder.mutation<CourseEnrollment, CourseEnrollmentRequest>({
      query: (enrollmentData) => ({
        url: '/enrollments/',
        method: 'POST',
        body: enrollmentData,
      }),
      invalidatesTags: ['CourseEnrollment', 'StudentVideoCourse', 'StudentVideoAnalytics'],
    }),

    getMyVideoEnrollments: builder.query<{message: string, data: CourseEnrollment[]}, string>({
      query: (userId) => `/users/${userId}/enrolled/`,
      providesTags: ['CourseEnrollment'],
    }),
    // ===== COURSE PROGRESS =====
    
    getVideoCourseProgress: builder.query<{message: string, data: StudentCourseProgress}, {courseId: string, userId: string}>({
      query: ({courseId, userId}) => `/users/${userId}/progress/${courseId}/`,
      providesTags: (result, error, {courseId}) => [
        { type: 'VideoProgress', id: courseId },
      ],
    }),

    markChapterComplete: builder.mutation<{ message: string; success: boolean }, ChapterCompletion>({
      query: (data) => ({
        url: '/chapters/complete/',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['VideoProgress', 'CourseEnrollment', 'StudentVideoAnalytics'],
    }),

    // ===== COURSE CONTENT =====
    
    getVideoCourseSections: builder.query<StudentVideoSection[], string>({
      query: (courseId) => `/${courseId}/sections/`,
      providesTags: (result, error, courseId) => [
        { type: 'StudentVideoCourse', id: courseId },
      ],
    }),

    getSectionChapters: builder.query<StudentVideoChapter[], string>({
      query: (sectionId) => `/sections/${sectionId}/chapters/`,
      providesTags: ['StudentVideoCourse'],
    }),

    getChapterDetail: builder.query<StudentVideoChapter, string>({
      query: (chapterId) => `/chapters/${chapterId}/`,
      providesTags: ['StudentVideoCourse'],
    }),

    // Chapter Resources
    getChapterResources: builder.query<{ message: string; data: ChapterResource[] }, string>({
      query: (chapterId) => `/chapters/${chapterId}/resources/`,
      providesTags: (result, error, chapterId) => [
        { type: 'ChapterResource', id: chapterId },
      ],
    }),

    // Chapter Quiz  
    getChapterQuiz: builder.query<{ message: string; data: ChapterQuiz | null }, string>({
      query: (chapterId) => `/chapters/${chapterId}/quiz/`,
      providesTags: (result, error, chapterId) => [
        { type: 'ChapterQuiz', id: chapterId },
      ],
    }),

    // ===== NOTES & BOOKMARKS =====

    createNote: builder.mutation<StudentNote, Omit<StudentNote, 'id' | 'userId' | 'createdAt' | 'updatedAt'>>({
      query: (noteData) => ({
        url: '/notes/',
        method: 'POST',
        body: noteData,
      }),
      invalidatesTags: ['StudentNote'],
    }),

    createBookmark: builder.mutation<StudentBookmark, Omit<StudentBookmark, 'id' | 'userId' | 'createdAt'>>({
      query: (bookmarkData) => ({
        url: '/bookmarks/',
        method: 'POST',
        body: bookmarkData,
      }),
      invalidatesTags: ['StudentBookmark'],
    }),
    // ===== REVIEWS & RATINGS =====

    createCourseReview: builder.mutation<CourseReview, CreateReviewData>({
      query: (reviewData) => ({
        url: '/reviews/',
        method: 'POST',
        body: reviewData,
      }),
      invalidatesTags: ['CourseReview', 'StudentVideoCourse'],
    }),
    // ===== CERTIFICATES =====
    
    getMyCertificates: builder.query<CourseCertificate[], void>({
      query: () => '/certificates/',
      providesTags: ['CourseCertificate'],
    }),
    // ===== RECOMMENDATIONS =====
    // ===== ANALYTICS =====
    // ===== WISHLIST =====
    
    getWishlist: builder.query<StudentVideoCourse[], void>({
      query: () => '/wishlist/',
      providesTags: ['StudentVideoCourse'],
    }),

    addToWishlist: builder.mutation<void, string>({
      query: (courseId) => ({
        url: '/wishlist/',
        method: 'POST',
        body: { courseId },
      }),
      invalidatesTags: ['StudentVideoCourse'],
    }),
  }),
});

// Export hooks
export const {
  // Course discovery
  useGetAvailableVideoCoursesQuery,
  useGetVideoCourseByIdQuery,
  // Enrollment
  useEnrollInVideoCourseMutation,
  useGetMyVideoEnrollmentsQuery,
  // Progress
  useGetVideoCourseProgressQuery,
  useMarkChapterCompleteMutation,
  
  // Content
  useGetVideoCourseSectionsQuery,
  useGetSectionChaptersQuery,
  useGetChapterDetailQuery,
  useGetChapterResourcesQuery,
  useGetChapterQuizQuery,
  
  // Notes & Bookmarks
  useCreateNoteMutation,
  useCreateBookmarkMutation,
  // Reviews
  useCreateCourseReviewMutation,
  // Certificates
  useGetMyCertificatesQuery,
  // Recommendations
  // Analytics
  // Wishlist
  useGetWishlistQuery,
  useAddToWishlistMutation,
} = studentVideoCourseApiSlice;