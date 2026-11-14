"use client";

import { useEffect, useState } from "react";
import { subscricaoApi } from "@/src/domains/student/subscricao/api";
import { cursoApi } from "@/src/domains/student/curso/api";
import { perfilApi } from "@/src/domains/student/perfil/api";
import { progressoApi } from "@/src/domains/student/progresso/api";
import { conversaApi } from "@/src/domains/student/conversa/api";
import { avisosApi } from "@/src/domains/student/avisos/api";
import { opiniaoApi } from "@/src/domains/student/opiniao/api";
import { professorApi } from "@/src/domains/teacher/professor/api";
import { administracaoApi } from "@/src/domains/admin/administracao/api";
import { TypedUseSelectorHook, useDispatch, useSelector } from "react-redux";
import { combineReducers, configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import { setupListeners } from "@reduxjs/toolkit/query";
import globalReducer from "@/state";
import { authSlice } from "@/src/domains/auth";
import { apiSlice } from "@/redux/features/api/apiSlice";
import { api } from "@/state/api";
// New domain-based APIs
import { teacherPracticeApiSlice } from "@/src/domains/teacher/practice-courses/api";
import { teacherVideoCourseApiSlice } from "@/src/domains/teacher/video-courses/api";
import { studentPracticeApiSlice } from "@/src/domains/student/practice-courses/api";
import { studentVideoCourseApiSlice } from "@/src/domains/student/video-courses/api";
import { studentLeaderboardApiSlice } from "@/src/domains/student/leaderboard/api";
import { studentAchievementsApiSlice } from "@/src/domains/student/achievements/api";
import { adminApiSlice } from "@/src/domains/admin/api";
import { feedbackApi } from "@/src/domains/shared/feedback/api/feedbackApiSlice";
import courseEditorSlice from "@/redux/features/courseEditor/courseEditorSlice";

/* REDUX STORE */
const rootReducer = combineReducers({
  global: globalReducer,
  auth: authSlice,
  courseEditor: courseEditorSlice,
  // Legacy Django API (for auth and shared features)
  [apiSlice.reducerPath]: apiSlice.reducer,
  // Legacy API for billing and transactions
  [api.reducerPath]: api.reducer,
  // New separated APIs
  [teacherPracticeApiSlice.reducerPath]: teacherPracticeApiSlice.reducer,
  [teacherVideoCourseApiSlice.reducerPath]: teacherVideoCourseApiSlice.reducer,
  [studentPracticeApiSlice.reducerPath]: studentPracticeApiSlice.reducer,
  [studentVideoCourseApiSlice.reducerPath]: studentVideoCourseApiSlice.reducer,
  [studentLeaderboardApiSlice.reducerPath]: studentLeaderboardApiSlice.reducer,
  [studentAchievementsApiSlice.reducerPath]: studentAchievementsApiSlice.reducer,
  [adminApiSlice.reducerPath]: adminApiSlice.reducer,
  [feedbackApi.reducerPath]: feedbackApi.reducer,
  [subscricaoApi.reducerPath]: subscricaoApi.reducer,
  [cursoApi.reducerPath]: cursoApi.reducer,
  [perfilApi.reducerPath]: perfilApi.reducer,
  [progressoApi.reducerPath]: progressoApi.reducer,
  [conversaApi.reducerPath]: conversaApi.reducer,
  [avisosApi.reducerPath]: avisosApi.reducer,
  [opiniaoApi.reducerPath]: opiniaoApi.reducer,
  [professorApi.reducerPath]: professorApi.reducer,
  [administracaoApi.reducerPath]: administracaoApi.reducer,
});

export const makeStore = () => {
  return configureStore({
    reducer: rootReducer,
    middleware: (getDefaultMiddleware) =>
      getDefaultMiddleware({
        serializableCheck: {
          ignoredActions: [
            "api/executeMutation/pending",
            "api/executeMutation/fulfilled", 
            "api/executeMutation/rejected",
            "apiSlice/executeMutation/pending",
            "apiSlice/executeMutation/fulfilled",
            "apiSlice/executeMutation/rejected",
          ],
          ignoredActionPaths: [
            "meta.arg.originalArgs.file",
            "meta.arg.originalArgs.audio_file",
            "meta.arg.originalArgs.formData",
            "payload.chapter.video",
            "meta.baseQueryMeta.request",
            "meta.baseQueryMeta.response",
          ],
          ignoredPaths: [
            "global.courseEditor.sections",
            "entities.videos.data",
            "meta.baseQueryMeta.request",
            "meta.baseQueryMeta.response",
          ],
        },
      })
      .concat(apiSlice.middleware)
      .concat(api.middleware)
      .concat(teacherPracticeApiSlice.middleware)
      .concat(teacherVideoCourseApiSlice.middleware)
      .concat(studentPracticeApiSlice.middleware)
      .concat(studentVideoCourseApiSlice.middleware)
      .concat(studentLeaderboardApiSlice.middleware)
      .concat(studentAchievementsApiSlice.middleware)
      .concat(adminApiSlice.middleware)
      .concat(feedbackApi.middleware)
      .concat(subscricaoApi.middleware)
      .concat(cursoApi.middleware)
      .concat(perfilApi.middleware)
      .concat(progressoApi.middleware)
      .concat(conversaApi.middleware)
      .concat(avisosApi.middleware)
      .concat(opiniaoApi.middleware)
      .concat(professorApi.middleware)
      .concat(administracaoApi.middleware),
  });
};

/* REDUX TYPES */
export type AppStore = ReturnType<typeof makeStore>;
export type RootState = ReturnType<AppStore["getState"]>;
export type AppDispatch = AppStore["dispatch"];
export const useAppDispatch = () => useDispatch<AppDispatch>();
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;

/* PROVIDER */
export default function StoreProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  // Uma store por montagem do provider; setupListeners devolve a função que os desliga.
  const [store] = useState<AppStore>(makeStore);
  useEffect(() => setupListeners(store.dispatch), [store]);
  return <Provider store={store}>{children}</Provider>;
}
