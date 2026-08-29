import java.util.HashMap;
import java.util.Map;

public class Student {
    private String name;
    private Map<String, Double> subjects;

    public Student(String name) {
        this.name = name;
        this.subjects = new HashMap<>();
    }

    public Student(String name, String subject, double grade) {
        this.name = name;
        this.subjects = new HashMap<>();
        this.subjects.put(subject, grade);
    }

    public String getName() {
        return name;
    }

    public Map<String, Double> getSubjects() {
        return subjects;
    }

    public void addSubject(String subject, double grade) {
        subjects.put(subject, grade);
    }

    public double getGrade(String subject) {
        return subjects.getOrDefault(subject, 0.0);
    }

    public String getSubject() {
        if (subjects.isEmpty()) {
            return "";
        }
        return subjects.keySet().iterator().next();
    }

    @Override
    public String toString() {
        StringBuilder sb = new StringBuilder(name + ": ");
        for (Map.Entry<String, Double> entry : subjects.entrySet()) {
            sb.append(entry.getKey()).append("=").append(entry.getValue()).append(" ");
        }
        return sb.toString().trim();
    }
}
