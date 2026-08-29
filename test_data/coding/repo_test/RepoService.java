// RepoEntity is in the same directory
import java.util.List;
import java.util.Map;

public interface RepoService {

    boolean add(RepoEntity entity);

    boolean delete(String id);

    RepoEntity getById(String id);

    List<RepoEntity> queryByDate(String nowDay);

    boolean approval(String id, String isApproval);

    Map<String, Object> getDictionary(String nowDay);

    // TODO: Add batchApprove(List<String> ids, String isApproval) method
    // Should approve multiple records at once, return success count
}
