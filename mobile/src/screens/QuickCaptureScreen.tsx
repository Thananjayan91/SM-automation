import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { RootStackParamList } from '../types';
import { apiTriggerGenerate, apiSubmitSource } from '../api/generator';
import { Colors, Spacing, Typography } from '../constants/theme';
import { Ionicons } from '@expo/vector-icons';

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const TONE_PRESETS = [
  'Authoritative & Insightful',
  'Casual & Conversational',
  'Direct & Punchy',
  'Inspirational',
];

const LANGUAGE_OPTIONS: { key: 'english' | 'tamil' | 'sinhala'; label: string }[] = [
  { key: 'english', label: 'English' },
  { key: 'tamil', label: 'தமிழ் (Tamil)' },
  { key: 'sinhala', label: 'සිංහල (Sinhala)' },
];

export const QuickCaptureScreen = () => {
  const navigation = useNavigation<NavigationProp>();
  const [mode, setMode] = useState<'topic' | 'url'>('topic');
  const [topic, setTopic] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [notes, setNotes] = useState('');
  const [selectedTone, setSelectedTone] = useState(TONE_PRESETS[0]);
  const [selectedLanguage, setSelectedLanguage] = useState<'english' | 'tamil' | 'sinhala'>('english');
  const [generating, setGenerating] = useState(false);

  const handleStartGeneration = async () => {
    if (mode === 'topic' && !topic.trim()) {
      Alert.alert('Required', 'Please enter a topic headline or idea prompt.');
      return;
    }
    if (mode === 'url' && !sourceUrl.trim()) {
      Alert.alert('Required', 'Please enter a valid web article URL.');
      return;
    }

    setGenerating(true);
    try {
      let sourceId: string | undefined = undefined;

      if (mode === 'url') {
        const srcRes = await apiSubmitSource({
          source_type: 'url',
          source_url: sourceUrl.trim(),
          headline: topic.trim() || undefined,
          notes: notes.trim() || undefined,
          tone_instruction: selectedTone,
        });

        if (!srcRes.data) {
          Alert.alert('Error', srcRes.error || 'Failed to submit article source.');
          setGenerating(false);
          return;
        }
        sourceId = srcRes.data.id;
      }

      // Trigger asynchronous generation job
      const genRes = await apiTriggerGenerate(
        mode === 'topic' ? topic.trim() : undefined,
        sourceId,
        undefined,
        selectedLanguage,
        selectedTone
      );

      if (genRes.data) {
        setGenerating(false);
        // Reset fields
        setTopic('');
        setSourceUrl('');
        setNotes('');
        // Navigate to live progress screen
        navigation.navigate('GenerationProgress', { jobId: genRes.data.id });
      } else {
        Alert.alert('Generation Error', genRes.error || 'Failed to dispatch AI generation.');
        setGenerating(false);
      }
    } catch (err: any) {
      Alert.alert('Error', err.message || 'An unexpected error occurred.');
      setGenerating(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>AI Post Studio</Text>
        <Text style={styles.subtitle}>Transform any topic or link into a published social asset</Text>
      </View>

      {/* Mode Selector */}
      <View style={styles.modeTabs}>
        <TouchableOpacity
          style={[styles.modeTab, mode === 'topic' && styles.modeTabActive]}
          onPress={() => setMode('topic')}
        >
          <Ionicons
            name="bulb-outline"
            size={16}
            color={mode === 'topic' ? Colors.primary : Colors.textMuted}
          />
          <Text style={[styles.modeTabText, mode === 'topic' && styles.modeTabTextActive]}>
            Topic / Idea
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.modeTab, mode === 'url' && styles.modeTabActive]}
          onPress={() => setMode('url')}
        >
          <Ionicons
            name="link-outline"
            size={16}
            color={mode === 'url' ? Colors.primary : Colors.textMuted}
          />
          <Text style={[styles.modeTabText, mode === 'url' && styles.modeTabTextActive]}>
            Article URL
          </Text>
        </TouchableOpacity>
      </View>

      {/* Main Input Card */}
      <View style={styles.card}>
        {mode === 'topic' ? (
          <View>
            <Text style={styles.label}>Topic or Headline *</Text>
            <TextInput
              style={styles.textInput}
              placeholder="e.g. 5 AI automation trends reshaping small business marketing in 2026"
              value={topic}
              onChangeText={setTopic}
              multiline
              numberOfLines={3}
            />
          </View>
        ) : (
          <View>
            <Text style={styles.label}>Article URL *</Text>
            <TextInput
              style={styles.singleInput}
              placeholder="https://techcrunch.com/article..."
              value={sourceUrl}
              onChangeText={setSourceUrl}
              autoCapitalize="none"
              keyboardType="url"
            />

            <Text style={[styles.label, { marginTop: Spacing.md }]}>Optional Headline</Text>
            <TextInput
              style={styles.singleInput}
              placeholder="Brief summary or focus angle"
              value={topic}
              onChangeText={setTopic}
            />
          </View>
        )}

        {/* Language Toggle Selector */}
        <Text style={[styles.label, { marginTop: Spacing.md }]}>Output Language</Text>
        <View style={styles.toneWrap}>
          {LANGUAGE_OPTIONS.map((lang) => {
            const isSelected = selectedLanguage === lang.key;
            return (
              <TouchableOpacity
                key={lang.key}
                style={[styles.tonePill, isSelected && styles.tonePillActive]}
                onPress={() => setSelectedLanguage(lang.key)}
              >
                <Text style={[styles.tonePillText, isSelected && styles.tonePillTextActive]}>
                  {lang.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Tone Selector */}
        <Text style={[styles.label, { marginTop: Spacing.md }]}>Tone & Voice</Text>
        <View style={styles.toneWrap}>
          {TONE_PRESETS.map((t) => {
            const isSelected = selectedTone === t;
            return (
              <TouchableOpacity
                key={t}
                style={[styles.tonePill, isSelected && styles.tonePillActive]}
                onPress={() => setSelectedTone(t)}
              >
                <Text style={[styles.tonePillText, isSelected && styles.tonePillTextActive]}>
                  {t}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Additional Notes / Guidance */}
        <Text style={[styles.label, { marginTop: Spacing.md }]}>Extra Instructions (Optional)</Text>
        <TextInput
          style={styles.textInput}
          placeholder="e.g. Mention our upcoming webinar, include 3 specific action tips"
          value={notes}
          onChangeText={setNotes}
          multiline
          numberOfLines={2}
        />
      </View>

      {/* Action Button */}
      <TouchableOpacity
        style={[styles.generateButton, generating && styles.buttonDisabled]}
        onPress={handleStartGeneration}
        disabled={generating}
      >
        {generating ? (
          <ActivityIndicator color="#ffffff" />
        ) : (
          <View style={styles.btnContent}>
            <Ionicons name="sparkles" size={18} color="#ffffff" />
            <Text style={styles.generateButtonText}>Generate Full Post Draft</Text>
          </View>
        )}
      </TouchableOpacity>

      <View style={styles.pipelineInfo}>
        <Ionicons name="information-circle-outline" size={14} color={Colors.textMuted} />
        <Text style={styles.pipelineInfoText}>
          Generates citations, 3 caption variants, hashtags, and a 1080x1080 banner.
        </Text>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    padding: Spacing.md,
    paddingBottom: Spacing.xl,
  },
  header: {
    marginBottom: Spacing.md,
  },
  title: {
    ...Typography.header,
  },
  subtitle: {
    ...Typography.caption,
    color: Colors.textMuted,
    marginTop: 2,
  },
  modeTabs: {
    flexDirection: 'row',
    backgroundColor: '#f1f5f9',
    borderRadius: 14,
    padding: 4,
    marginBottom: Spacing.md,
  },
  modeTab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 10,
  },
  modeTabActive: {
    backgroundColor: Colors.surface,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 2,
    elevation: 2,
  },
  modeTabText: {
    fontSize: 13,
    fontWeight: '600',
    color: Colors.textMuted,
  },
  modeTabTextActive: {
    color: Colors.primary,
  },
  card: {
    backgroundColor: Colors.surface,
    borderRadius: 16,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.md,
  },
  label: {
    fontSize: 12,
    fontWeight: '700',
    color: Colors.text,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  singleInput: {
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: Colors.text,
  },
  textInput: {
    backgroundColor: '#f8fafc',
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: Colors.text,
    textAlignVertical: 'top',
  },
  toneWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  tonePill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: '#f1f5f9',
    borderWidth: 1,
    borderColor: 'transparent',
  },
  tonePillActive: {
    backgroundColor: Colors.primaryLight,
    borderColor: Colors.primary,
  },
  tonePillText: {
    fontSize: 12,
    color: Colors.textMuted,
    fontWeight: '500',
  },
  tonePillTextActive: {
    color: Colors.primary,
    fontWeight: '700',
  },
  generateButton: {
    backgroundColor: Colors.primary,
    paddingVertical: 15,
    borderRadius: 14,
    alignItems: 'center',
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 4,
  },
  buttonDisabled: {
    opacity: 0.7,
  },
  btnContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  generateButtonText: {
    color: '#ffffff',
    fontSize: 15,
    fontWeight: '700',
  },
  pipelineInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: Spacing.sm,
  },
  pipelineInfoText: {
    fontSize: 11,
    color: Colors.textMuted,
  },
});

